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
from pathlib import Path
from typing import Optional

import json
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import uuid
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from main import build_graph
from state import VendorDueDiligenceState

# Global session cache removed for stateless API chat follow-ups

# Reuse the battle-tested ingestion functions from ingest.py
from ingest import (
    build_chunk_hierarchy,
    generate_child_embeddings,
    get_embedding_model,
    get_supabase_client,
    load_pdf,
    insert_into_supabase,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
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

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verifies the Supabase JWT token and extracts the user_id."""
    token = credentials.credentials
    db = get_supabase_client()
    try:
        res = db.auth.get_user(token)
        if not res or not res.user:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return res.user.id
    except Exception as e:
        log.error("Authentication failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# ---------------------------------------------------------------------------
# Startup: Compile the graph and warm up heavy models once
# ---------------------------------------------------------------------------
log.info("Compiling LangGraph pipeline...")
graph_app = build_graph()
log.info("Pipeline compiled successfully.")

log.info("Warming up embedding model for upload endpoint...")
embedding_model = get_embedding_model()
log.info("Embedding model ready.")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    vendor_name: str
    vendor_url: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: Run the full due diligence pipeline
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/analyze")
async def analyze_vendor(request: AnalyzeRequest, user_id: str = Depends(get_current_user)):
    """
    Triggers the LangGraph pipeline to perform due diligence on a vendor,
    then saves the initial risk_assessment to the audits table.
    """
    log.info(f"Received analysis request for vendor: {request.vendor_name} by user {user_id}")

    async def event_generator():
        try:
            initial_state: VendorDueDiligenceState = {  # type: ignore[typeddict-item]
                "vendor_name": request.vendor_name,
                "vendor_url": request.vendor_url or "",
            }

            yield json.dumps({"type": "progress", "message": "Initializing analysis..."}) + "\n"

            final_assessment = None
            
            # Stream events as nodes complete
            async for event in graph_app.astream(initial_state, stream_mode="updates"):
                for node_name, state_update in event.items():
                    msg = "Processing..."
                    if node_name == "osint_agent":
                        msg = "[OSINT Agent] Completed web reconnaissance..."
                    elif node_name == "rag_agent":
                        msg = "[RAG Agent] Extracted policy discrepancies..."
                    elif node_name == "judge_agent":
                        msg = "[Judge Agent] Finalizing risk assessment..."
                        final_assessment = state_update.get("risk_assessment")
                        
                    yield json.dumps({"type": "progress", "node": node_name, "message": msg}) + "\n"

            if not final_assessment:
                yield json.dumps({"type": "error", "message": "Pipeline completed but no risk assessment was generated."}) + "\n"
                return

            # Deduplication and Versioning Logic
            db = get_supabase_client()
            
            # Fetch all past audits for this user and base vendor (like "Meta%")
            base_vendor = request.vendor_name
            # Remove any existing (vX) suffix if the user typed it
            import re
            base_vendor = re.sub(r'\s*\(v\d+\)$', '', base_vendor).strip()
            
            res = db.table("audits").select("session_id, vendor_name, risk_assessment").eq("user_id", user_id).ilike("vendor_name", f"{base_vendor}%").execute()
            
            existing_audits = res.data or []
            
            # Check for identical analysis
            import json as json_lib
            new_assessment_str = json_lib.dumps(final_assessment, sort_keys=True)
            
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
                    
                # Check for identical content
                if json_lib.dumps(audit["risk_assessment"], sort_keys=True) == new_assessment_str:
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


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: Upload a PDF policy document for RAG ingestion
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/upload_policy")
async def upload_policy(
    file: UploadFile = File(...),
    role: str = Form(...)
):
    """
    Accepts a PDF document and a role ('internal' or 'vendor'), processes it 
    through the ingestion pipeline (parse → chunk → embed → insert into Supabase).
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
    log.info("Upload received: %s (size: %s)", file.filename, file.size)
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

        # Stage 1: Load the PDF pages with the role metadata
        pages = load_pdf(Path(tmp_path), role)

        if not pages:
            raise HTTPException(status_code=400, detail="PDF appears to be empty or unreadable.")

        # Stage 2: Build parent/child chunk hierarchy
        hierarchy = build_chunk_hierarchy(pages)

        # Stage 3: Generate embeddings for all child chunks
        generate_child_embeddings(hierarchy, embedding_model)

        # Stage 4: Insert into Supabase
        db = get_supabase_client()
        insert_into_supabase(hierarchy, db)

        # Calculate total chunks ingested
        total_parents = len(hierarchy)
        total_children = sum(len(p["children"]) for p in hierarchy)

        log.info(
            "✅ Ingestion complete for '%s': %d parents, %d children.",
            file.filename, total_parents, total_children,
        )

        return {
            "status": "success",
            "filename": file.filename,
            "pages_parsed": len(pages),
            "parent_chunks": total_parents,
            "child_chunks": total_children,
            "total_chunks_ingested": total_parents + total_children,
        }

    except HTTPException:
        raise  # Re-raise our own validation errors cleanly
    except Exception as e:
        log.error("Ingestion failed for '%s': %s", file.filename, e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    finally:
        # CRITICAL: Always delete the temp file, even if the pipeline explodes.
        # In ephemeral containers (HF Spaces, Cloud Run), disk is finite and
        # not cleaned between requests. Leaked files accumulate and eventually
        # crash the container with "No space left on device."
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
            log.info("Cleaned up temp file: %s", tmp_path)


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: Health check
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/health")
async def health_check():
    """Simple health check endpoint for Cloud Run / load balancers."""
    return {"status": "healthy"}


# Global Chat Agent
from chat_agent import ChatAgent
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
            user_msg=request.message
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



# ============================================================
# 🧠 Mentor Notes: Handling Files in Containers
# ============================================================
#
# WHY THE `finally` BLOCK IS NON-NEGOTIABLE
# ──────────────────────────────────────────
# Our backend runs inside ephemeral containers (Hugging Face Spaces,
# Google Cloud Run). These environments have critical constraints:
#
# 1. LIMITED DISK SPACE
#    Container filesystems are typically 1–10 GB. Unlike your MacBook,
#    there is no garbage collection daemon cleaning up after you.
#    Every file you write stays until *you* delete it or the container
#    is destroyed and re-created.
#
# 2. PERSISTENT ACROSS REQUESTS
#    A single container instance handles many sequential requests.
#    If each request saves a 5 MB PDF and forgets to delete it,
#    after 200 requests you've consumed 1 GB of disk. After 2000
#    requests, you've crashed the container with ENOSPC.
#
# 3. CRASH-SAFE CLEANUP
#    The `try/finally` pattern guarantees the temp file is removed
#    even if the embedding model throws an OOM error, Supabase
#    times out, or any other exception occurs mid-pipeline.
#    Without `finally`, an exception in Stage 3 would skip the
#    cleanup code and leak the file permanently.
#
# 4. WHY NOT `delete=True` IN NamedTemporaryFile?
#    With `delete=True`, the file is deleted when the file handle
#    closes. But our pipeline needs to *re-open* the file via
#    PyPDFLoader (which takes a file path, not a handle). If we
#    let the context manager delete it on close, the loader would
#    find an empty path. So we use `delete=False` and manage the
#    lifecycle ourselves in `finally`.
#
# TLDR: In containers, treat disk like RAM — allocate carefully,
# free explicitly, and never assume someone else will clean up.
# ============================================================

