"""
api.py — FastAPI wrapper for the Vendor Due Diligence LangGraph Pipeline

This module exposes our agentic pipeline as a REST API.
Run it locally with: uvicorn api:app --reload

Endpoints:
    POST /analyze         — Run full OSINT + RAG + Judge pipeline for a vendor.
    POST /upload_policy   — Upload a PDF policy document for RAG ingestion.
    GET  /health          — Simple health check.
"""

import logging
import os
import tempfile
from typing import Optional
import uuid

import json
import asyncio
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_google_genai import ChatGoogleGenerativeAI
from redis import Redis
from rq import Queue

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from main import build_graph
from state import VendorDueDiligenceState
from ingest import process_ingestion_job, get_embedding_model, get_supabase_client
from chat_agent import ChatAgent

# Initialize OpenTelemetry
provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Global session cache removed for stateless API chat follow-ups

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_conn = Redis.from_url(redis_url)
ingest_queue = Queue('ingestion_queue', connection=redis_conn)

# Logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

# FastAPI App
app = FastAPI(
    title="Trust Agent - Vendor Due Diligence API",
    description="API for running automated vendor due diligence using LangGraph.",
    version="1.0.0"
)

# Enable CORS so frontend apps (localhost, Firebase, etc.) can call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten this in production to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument the FastAPI app with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verifies the Supabase JWT token and extracts the user_id, with retries for network timeouts."""
    token = credentials.credentials
    db = get_supabase_client()
    import time
    for attempt in range(3):
        try:
            res = db.auth.get_user(token)
            if not res or not res.user:
                raise HTTPException(status_code=401, detail="Invalid authentication credentials")
            return res.user.id
        except Exception as e:
            if attempt == 2:
                log.error("Authentication failed after 3 attempts: %s", e)
                raise HTTPException(status_code=401, detail="Invalid authentication credentials")
            time.sleep(0.5)

# Startup: Compile the graph and warm up heavy models once
log.info("Compiling LangGraph pipeline...")
graph_app = build_graph()
log.info("Pipeline compiled successfully.")

log.info("Warming up embedding model for upload endpoint...")
embedding_model = get_embedding_model()
log.info("Embedding model ready.")

# Schemas
class AnalyzeRequest(BaseModel):
    vendor_name: str
    vendor_url: Optional[str] = None


# Run the full due diligence pipeline
@app.post("/analyze")
async def analyze_vendor(request: AnalyzeRequest, user_id: str = Depends(get_current_user)):
    """
    Triggers the LangGraph pipeline to perform due diligence on a vendor,
    then saves the initial risk_assessment to the audits table.
    """
    log.info(f"Received analysis request for vendor: {request.vendor_name} by user {user_id}")

    async def event_generator():
        try:
            initial_state: VendorDueDiligenceState = {
                "user_id": user_id,
                "vendor_name": request.vendor_name,
                "vendor_url": request.vendor_url or "",
            }

            yield json.dumps({"type": "progress", "message": "Initializing analysis..."}) + "\n"

            final_assessment = None
            raw_osint = []
            raw_rag = []
            raw_rag_clauses = []
            
            # Stream events as nodes complete
            async for event in graph_app.astream(initial_state, stream_mode="updates"):
                for node_name, state_update in event.items():
                    msg = "Processing..."
                    if node_name == "osint_agent":
                        msg = "[OSINT Agent] Completed web reconnaissance..."
                        raw_osint = state_update.get("osint_findings", [])
                    elif node_name == "comparator_agent":
                        msg = "[Comparator Agent] Extracted policy discrepancies..."
                        raw_rag = state_update.get("rag_findings", [])
                        raw_rag_clauses = state_update.get("raw_rag_clauses", [])
                    elif node_name == "judge_agent":
                        msg = "[Judge Agent] Finalizing risk assessment..."
                        final_assessment = state_update.get("risk_assessment")
                        
                    yield json.dumps({"type": "progress", "node": node_name, "message": msg}) + "\n"

            if not final_assessment:
                yield json.dumps({"type": "error", "message": "Pipeline completed but no risk assessment was generated."}) + "\n"
                return

            # Attach raw data for sandbox what-if analysis
            final_assessment["raw_osint_findings"] = raw_osint
            final_assessment["rag_findings"] = raw_rag
            final_assessment["raw_rag_clauses"] = raw_rag_clauses

            # Deduplication and Versioning Logic
            db = get_supabase_client()
            
            # Fetch all past audits for this user and base vendor (like "Meta%")
            base_vendor = request.vendor_name
            # Remove any existing (vX) suffix if the user typed it
            import re
            base_vendor = re.sub(r'\s*\(v\d+\)$', '', base_vendor).strip()
            
            res = db.table("audits").select("session_id, vendor_name, risk_assessment").eq("user_id", user_id).ilike("vendor_name", f"{base_vendor}%").execute()
            
            existing_audits = res.data or []
            
            # Check for identical raw findings (ignore Judge Agent LLM variations)
            import json as json_lib
            
            def get_raw_fingerprint(assessment):
                return json_lib.dumps({
                    "osint": assessment.get("raw_osint_findings", []),
                    "rag": assessment.get("rag_findings", [])
                }, sort_keys=True)

            new_raw_fingerprint = get_raw_fingerprint(final_assessment)
            
            identical_session = None
            max_version = 0
            
            for audit in existing_audits:
                v_name = audit["vendor_name"]
                # Parse version number to keep track
                match = re.search(r'\(v(\d+)\)$', v_name)
                if match:
                    max_version = max(max_version, int(match.group(1)))
                elif v_name.lower() == base_vendor.lower():
                    max_version = max(max_version, 1)
                    
                # Check for identical raw content
                if get_raw_fingerprint(audit["risk_assessment"]) == new_raw_fingerprint:
                    identical_session = audit["session_id"]
            
            if identical_session:
                # If identical, just use the existing session and update its timestamp
                # Note: Supabase doesn't easily let us update created_at via API if it's auto-generated,
                # but we can return the existing session so it doesn't create duplicates.
                # Actually, let's just return it. The frontend sorts by created_at natively? Yes.
                # To push it to top, let's update chat_history (no-op) which updates modified_at if we had one,
                # but we'll just return the session_id so frontend can open it.
                yield json.dumps({
                    "type": "complete",
                    "vendor": request.vendor_name,
                    "session_id": identical_session,
                    "risk_assessment": final_assessment,
                    "deduplicated": True
                }) + "\n"
                return

            # If different, append a version tag if this vendor already exists
            final_vendor_name = base_vendor
            if max_version > 0:
                final_vendor_name = f"{base_vendor} (v{max_version + 1})"
                
            session_id = str(uuid.uuid4())
            
            # Save to Supabase
            db.table("audits").insert({
                "session_id": session_id,
                "user_id": user_id,
                "vendor_name": final_vendor_name,
                "risk_assessment": final_assessment,
                "chat_history": []
            }).execute()

            yield json.dumps({
                "type": "complete",
                "vendor": final_vendor_name,
                "session_id": session_id,
                "risk_assessment": final_assessment
            }) + "\n"

        except Exception as e:
            error_str = str(e)
            log.error(f"Error during pipeline execution: {error_str}")
            
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                friendly_detail = "Google AI Free Tier rate limit exceeded. Please wait about 30 seconds and try again."
            else:
                friendly_detail = "An unexpected error occurred while analyzing the vendor. Please try again."
                
            yield json.dumps({"type": "error", "message": friendly_detail}) + "\n"

    return StreamingResponse(
        event_generator(), 
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# Upload a PDF policy document for RAG ingestion
@app.post("/upload_policy")
async def upload_policy(
    file: UploadFile = File(...),
    role: str = Form(...),
    vendor_name: str = Form(""),
    user_id: str = Depends(get_current_user)
):
    """
    Accepts a PDF document and a role ('internal' or 'vendor'), processes it 
    through the ingestion pipeline (parse → chunk → embed → insert into Supabase).
    Requires authentication to scope documents to the user.
    """
    if role not in ["internal", "vendor"]:
        raise HTTPException(
            status_code=400,
            detail="Role must be exactly 'internal' or 'vendor'."
        )

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf document."
        )

    log.info("=" * 50)
    log.info("Upload received: %s (size: %s, user: %s)", file.filename, file.size, user_id)
    log.info("=" * 50)

    # Save the uploaded file to a secure temporary location.
    # The `finally` block guarantees cleanup even if the pipeline crashes,
    # which is critical in ephemeral containers with limited disk space.
    tmp_path: str | None = None

    try:
        # Write the uploaded bytes to a temp file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf",
            prefix="upload_",
        ) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        log.info("Saved to temp file: %s", tmp_path)

        # Enqueue the background ingestion task
        job = ingest_queue.enqueue(
            process_ingestion_job, 
            tmp_path, 
            role, 
            user_id, 
            vendor_name,
            job_timeout=3600
        )

        log.info("✅ Ingestion job queued for '%s': %s", file.filename, job.id)

        return {
            "status": "processing",
            "filename": file.filename,
            "job_id": job.id,
            "message": "Document queued for asynchronous ingestion."
        }

    except HTTPException:
        raise  # Re-raise our own validation errors cleanly
    except Exception as e:
        log.error("Ingestion failed to queue for '%s': %s", file.filename, e)
        # Note: We manually delete tmp_path here because the job wasn't queued.
        # If it WAS queued, the worker deletes it in process_ingestion_job.
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

# SSE Progress Tracking for Uploads
@app.get("/upload_progress/{job_id}")
async def upload_progress(job_id: str):
    """
    Server-Sent Events (SSE) endpoint to stream real-time progress
    of a background ingestion job.
    """
    async def event_generator():
        pubsub = redis_conn.pubsub()
        channel = f"ingest_progress:{job_id}"
        pubsub.subscribe(channel)
        
        try:
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = message["data"].decode("utf-8")
                    yield f"data: {data}\n\n"
                    
                    # If progress reaches 100 or -1, close the stream
                    try:
                        parsed = json.loads(data)
                        if parsed.get("progress") in (100, -1):
                            break
                    except Exception:
                        pass
                        
                await asyncio.sleep(0.1)
        finally:
            pubsub.unsubscribe(channel)
            
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Health check
@app.get("/health")
async def health_check():
    """Simple health check endpoint for Cloud Run / load balancers."""
    return {"status": "healthy"}


# Global Chat Agent
chat_agent_instance = ChatAgent()

@app.get("/audits")
async def get_audits(user_id: str = Depends(get_current_user)):
    """Fetches all past audits for the authenticated user from Supabase."""
    db = get_supabase_client()
    try:
        res = db.table("audits").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return {"status": "success", "audits": res.data}
    except Exception as e:
        log.error(f"Error fetching audits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """
    Conversational endpoint to ask follow-up questions about an analysis.
    Fetches context and history from Supabase, calls the agent, and appends the response.
    """
    try:
        db = get_supabase_client()
        
        # Verify ownership and fetch data
        res = db.table("audits").select("*").eq("session_id", request.session_id).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Audit session not found")
        
        audit_data = res.data[0]
        vendor_name = audit_data["vendor_name"]
        
        # Format context for the LLM
        risk = audit_data["risk_assessment"]
        context_str = f"OSINT Reconnaissance:\n{chr(10).join(risk.get('osint_inferences', []))}\n\nRAG Policy Discrepancies:\n{chr(10).join(risk.get('rag_inferences', []))}\n\nComparative Analysis:\n{risk.get('comparative_analysis', '')}"
        
        history = audit_data["chat_history"]
        
        # Call the ChatAgent
        response_text = chat_agent_instance.invoke(
            vendor_name=vendor_name,
            context=context_str,
            history=history,
            user_msg=request.message,
            session_id=request.session_id,
            user_id=user_id
        )
        
        # Update database with new history
        new_history = history + [
            {"role": "user", "content": request.message},
            {"role": "agent", "content": response_text}
        ]
        
        db.table("audits").update({"chat_history": new_history}).eq("session_id", request.session_id).execute()
        
        return {"status": "success", "response": response_text}
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        log.error("Chat endpoint failed: %s", error_str)
        
        # Translate raw LLM errors into friendly messages
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            friendly_detail = "I am currently experiencing high traffic (Google AI Rate Limit). Please wait 30 seconds and try asking again!"
        else:
            friendly_detail = "An unexpected system error occurred while generating a response. Please try again."
            
        raise HTTPException(status_code=500, detail=friendly_detail)


class RemediationRequest(BaseModel):
    session_id: str

@app.post("/generate_remediation")
async def generate_remediation(request: RemediationRequest, user_id: str = Depends(get_current_user)):
    """
    Takes an existing audit session and generates a highly professional, 
    actionable remediation email to the vendor citing the specific RAG/OSINT discrepancies.
    """
    try:
        db = get_supabase_client()
        
        # Verify ownership and fetch data
        res = db.table("audits").select("*").eq("session_id", request.session_id).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Audit session not found")
        
        audit_data = res.data[0]
        vendor_name = audit_data["vendor_name"]
        risk = audit_data["risk_assessment"]
        
        # Format context for the LLM
        osint = chr(10).join(f"- {i}" for i in risk.get('osint_inferences', []))
        rag = chr(10).join(f"- {i}" for i in risk.get('rag_inferences', []))
        gaps = chr(10).join(f"- {i}" for i in risk.get('data_gaps', []))
        
        prompt = f"""You are a Senior Vendor Security Analyst writing an actionable remediation request letter/email to the security team of a vendor named {vendor_name}.
        
Based on a recent technical risk review, we have identified the following discrepancies and concerns:

RAG Policy Discrepancies (highest priority):
{rag if rag else "None."}

External/OSINT Security Concerns:
{osint if osint else "None."}

Information/Data Gaps (missing policies we need from them):
{gaps if gaps else "None."}

Your task:
Draft a highly professional, structured, and polite email addressed to the {vendor_name} Security & Compliance Team.
- Clearly and precisely state the discrepancies found.
- Request clarification or proof of remediation for the identified deficiencies.
- Request any missing documentation listed in the data gaps.
- The tone must be strictly professional, corporate, and collaborative (not accusatory).
- Do not include brackets like [Your Name], just sign off as "Vendor Security & Risk Management Team".
- Output ONLY the email draft text. Do not include any meta-commentary.
"""

        # Call the LLM directly
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
        response = llm.invoke(prompt)
        
        return {"status": "success", "draft": response.content}
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        log.error("Remediation generation failed: %s", error_str)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            raise HTTPException(status_code=429, detail="AI Rate Limit Exceeded. Please try again in 30 seconds.")
        raise HTTPException(status_code=500, detail="Failed to generate remediation draft.")


# Compliance Gap Matrix — gap action tracking

class GapStatusUpdate(BaseModel):
    session_id: str
    gap_index: int
    category: str   # "osint" | "rag" | "data_gap"
    status: str     # "open" | "accepted" | "remediation" | "exemption"
    note: str = ""
    assigned_to: str | None = None


@app.post("/update_gap_status")
async def update_gap_status(request: GapStatusUpdate, user_id: str = Depends(get_current_user)):
    """
    Persists a user's action (Accept / Remediate / Exempt) on a specific
    compliance gap identified during analysis.
    """
    if request.status not in ("open", "accepted", "remediation", "exemption"):
        raise HTTPException(status_code=400, detail="Status must be one of: open, accepted, remediation, exemption")
    if request.category not in ("osint", "rag", "data_gap"):
        raise HTTPException(status_code=400, detail="Category must be one of: osint, rag, data_gap")

    try:
        db = get_supabase_client()

        # Fetch existing audit
        res = db.table("audits").select("risk_assessment").eq("session_id", request.session_id).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Audit session not found")

        risk = res.data[0]["risk_assessment"]

        # Initialize gap_actions array if it doesn't exist yet
        gap_actions: list = risk.get("gap_actions", [])

        # Find existing entry for this specific gap, or create a new one
        existing_idx = None
        for i, action in enumerate(gap_actions):
            if action.get("gap_index") == request.gap_index and action.get("category") == request.category:
                existing_idx = i
                break

        from datetime import datetime, timezone
        action_entry = {
            "gap_index": request.gap_index,
            "category": request.category,
            "status": request.status,
            "note": request.note,
            "assigned_to": request.assigned_to,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        if existing_idx is not None:
            gap_actions[existing_idx] = action_entry
        else:
            gap_actions.append(action_entry)

        risk["gap_actions"] = gap_actions

        # Write back
        db.table("audits").update({"risk_assessment": risk}).eq("session_id", request.session_id).execute()

        return {"status": "success", "gap_actions": gap_actions}

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to update gap status: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update gap status.")


@app.get("/gap_actions/{session_id}")
async def get_gap_actions(session_id: str, user_id: str = Depends(get_current_user)):
    """
    Returns the current gap_actions array for a given audit session.
    """
    try:
        db = get_supabase_client()
        res = db.table("audits").select("risk_assessment").eq("session_id", session_id).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Audit session not found")

        risk = res.data[0]["risk_assessment"]
        return {"status": "success", "gap_actions": risk.get("gap_actions", [])}

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to fetch gap actions: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch gap actions.")


# Policy Sandbox — "What-If" Analysis

class SandboxRequest(BaseModel):
    session_id: str
    disabled_clauses: list[str]  # Exact clause texts to filter out


@app.post("/sandbox_evaluate")
async def sandbox_evaluate(request: SandboxRequest, user_id: str = Depends(get_current_user)):
    """
    Re-runs the Comparator + Judge simulation by filtering out specific internal
    RAG clauses that the user has toggled off in the Policy Sandbox.
    Does NOT save the result; just returns the simulated risk assessment.
    """
    try:
        db = get_supabase_client()
        res = db.table("audits").select("vendor_name, risk_assessment").eq("session_id", request.session_id).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Audit session not found")

        audit = res.data[0]
        vendor_name = audit["vendor_name"]
        risk = audit["risk_assessment"]

        raw_osint = risk.get("raw_osint_findings", [])
        raw_rag_clauses = risk.get("raw_rag_clauses", [])

        if not raw_rag_clauses and not raw_osint:
            raise HTTPException(status_code=400, detail="This audit lacks raw data for sandbox simulation. Please re-run the analysis.")

        # Filter out disabled INTERNAL clauses by matching on clause_text
        disabled_set = set(request.disabled_clauses)
        surviving_clauses = [
            c for c in raw_rag_clauses
            if not (c.get("role") == "internal" and c.get("clause_text") in disabled_set)
        ]

        # Rebuild policy text from surviving clauses
        internal_text = "\n\n---\n\n".join(
            c.get("parent_context") or c.get("clause_text", "")
            for c in surviving_clauses if c.get("role") == "internal"
        )
        vendor_text = "\n\n---\n\n".join(
            c.get("parent_context") or c.get("clause_text", "")
            for c in surviving_clauses if c.get("role") == "vendor"
        )

        # Re-run the comparator's LLM analysis on filtered clauses
        from comparator_agent import run_policy_comparison
        findings, matrix = run_policy_comparison(vendor_name, internal_text, vendor_text)

        # Re-run the judge with fresh findings
        from judge_agent import judge_agent_node

        mock_state: VendorDueDiligenceState = {
            "user_id": user_id,
            "vendor_name": vendor_name,
            "vendor_url": "",
            "osint_findings": raw_osint,
            "osint_summary": "",
            "rag_findings": findings,
            "compliance_matrix": matrix,
            "raw_rag_clauses": surviving_clauses,
            "risk_assessment": None,
            "judge_reasoning": ""
        }

        result = judge_agent_node(mock_state)
        simulated_risk = result.get("risk_assessment")
        if not simulated_risk:
            raise HTTPException(status_code=500, detail="Simulated judge agent returned no result.")

        return {"status": "success", "simulated_risk": simulated_risk}

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to run sandbox evaluation: %s", e)
        raise HTTPException(status_code=500, detail="Failed to run policy sandbox evaluation.")

# Live Threat & Breach Feed

class WatchVendorRequest(BaseModel):
    vendor_name: str

@app.post("/watch_vendor")
async def watch_vendor(request: WatchVendorRequest, user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        db.table("watched_vendors").insert({
            "user_id": user_id,
            "vendor_name": request.vendor_name
        }).execute()
        return {"status": "success", "message": f"Now watching {request.vendor_name}"}
    except Exception as e:
        log.warning(f"Failed to watch vendor: {e}")
        return {"status": "success", "message": "Already watching"}

@app.delete("/watch_vendor/{vendor_name}")
async def unwatch_vendor(vendor_name: str, user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    db.table("watched_vendors").delete().eq("user_id", user_id).eq("vendor_name", vendor_name).execute()
    return {"status": "success"}

@app.get("/watched_vendors")
async def get_watched_vendors(user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        res = db.table("watched_vendors").select("vendor_name, created_at").eq("user_id", user_id).execute()
        return {"watched_vendors": res.data or []}
    except Exception as e:
        log.error(f"Failed to fetch watched vendors: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch watched vendors. Did you run the SQL migration?")



@app.delete("/audits/{session_id}")
async def delete_audit(session_id: str, user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        # First verify the audit belongs to the user
        audit_check = db.table("audits").select("session_id").eq("session_id", session_id).eq("user_id", user_id).execute()
        if not audit_check.data:
            raise HTTPException(status_code=404, detail="Audit not found")

        # Delete the audit itself. Child tables like chat_messages or gap_actions do not exist (they are JSONB columns).
        db.table("audits").delete().eq("session_id", session_id).eq("user_id", user_id).execute()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete audit: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete audit.")

@app.get("/threat_alerts")
async def get_threat_alerts(user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        res = db.table("threat_alerts").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return {"alerts": res.data or []}
    except Exception as e:
        log.error(f"Failed to fetch threat alerts: {e}")
        # Return a clean JSON 500 error instead of letting FastAPI crash
        raise HTTPException(status_code=500, detail="Failed to fetch threat alerts. Did you run the SQL migration for Phase 4?")

@app.post("/threat_alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        db.table("threat_alerts").update({"is_read": True}).eq("id", alert_id).eq("user_id", user_id).execute()
        return {"status": "success"}
    except Exception as e:
        log.error(f"Failed to mark alert as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark alert as read.")

# Employees / Team Management

class EmployeeCreate(BaseModel):
    name: str
    position: str

@app.get("/employees")
async def get_employees(user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        res = db.table("employees").select("*").eq("user_id", user_id).order("created_at").execute()
        return {"employees": res.data or []}
    except Exception as e:
        log.error(f"Failed to fetch employees: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch employees.")

@app.post("/employees")
async def create_employee(emp: EmployeeCreate, user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        res = db.table("employees").insert({
            "user_id": user_id,
            "name": emp.name,
            "position": emp.position
        }).execute()
        return res.data[0]
    except Exception as e:
        log.error(f"Failed to create employee: {e}")
        raise HTTPException(status_code=500, detail="Failed to create employee.")

@app.delete("/employees/{employee_id}")
async def delete_employee(employee_id: str, user_id: str = Depends(get_current_user)):
    db = get_supabase_client()
    try:
        db.table("employees").delete().eq("id", employee_id).eq("user_id", user_id).execute()
        return {"status": "success"}
    except Exception as e:
        log.error(f"Failed to delete employee: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete employee.")


# Ensure temp file cleanup in ephemeral environments to prevent disk leaks.

