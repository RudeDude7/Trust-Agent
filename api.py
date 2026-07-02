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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import uuid
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from main import build_graph
from state import VendorDueDiligenceState

# Global session cache for stateless API chat follow-ups
sessions: dict[str, VendorDueDiligenceState] = {}

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
async def analyze_vendor(request: AnalyzeRequest):
    """
    Triggers the LangGraph pipeline to perform due diligence on a vendor.
    """
    log.info(f"Received analysis request for vendor: {request.vendor_name}")

    try:
        # Construct the initial state
        initial_state: VendorDueDiligenceState = {  # type: ignore[typeddict-item]
            "vendor_name": request.vendor_name,
            "vendor_url": request.vendor_url or "",
        }

        # Invoke the graph synchronously (since our agents use synchronous LangChain calls right now)
        # In a high-traffic production system, we would convert the node functions to async.
        final_state = graph_app.invoke(initial_state)

        # Extract the final assessment
        assessment = final_state.get("risk_assessment")
        if not assessment:
            raise HTTPException(status_code=500, detail="Pipeline completed but no risk assessment was generated.")

        session_id = str(uuid.uuid4())
        sessions[session_id] = final_state # type: ignore

        return {
            "status": "success",
            "vendor": request.vendor_name,
            "session_id": session_id,
            "risk_assessment": assessment
        }

    except Exception as e:
        log.error(f"Error during pipeline execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 4: Chat with the analysis results
# ═══════════════════════════════════════════════════════════════════════════
class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Conversational endpoint to ask follow-up questions about the analysis.
    Uses the session_id to retrieve the cached graph state.
    """
    state = sessions.get(request.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
        
    vendor_name = state.get("vendor_name", "unknown")
    rag_clauses = state.get("rag_clauses", [])
    osint_findings = state.get("osint_findings", [])
    
    # Construct context
    context_text = f"Vendor: {vendor_name}\n\nRAG Clauses:\n"
    for clause in rag_clauses:
        context_text += f"- (Role: {clause.get('role', 'unknown')}) {clause.get('clause_text')}\n"
    
    context_text += "\nOSINT Findings:\n"
    for finding in osint_findings:
        context_text += f"- [{finding.get('finding_type')}] {finding.get('title')}: {finding.get('snippet')}\n"

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant helping a user analyze a vendor due diligence report. "
                   "Answer the user's question using ONLY the provided context from the RAG and OSINT pipeline. "
                   "If the context does not contain the answer, say you do not know based on the current data.\n\n"
                   "=== CONTEXT ===\n{context}"),
        ("user", "{message}")
    ])
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
    chain = prompt | llm
    
    try:
        response = chain.invoke({"context": context_text, "message": request.message})
        return {"status": "success", "response": response.content}
    except Exception as e:
        log.error("Chat endpoint failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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

