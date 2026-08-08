"""
comparator_agent.py — Comparator Agent Node for the Vendor Due Diligence Pipeline

Performs vector similarity search against the Supabase document_chunks table,
retrieves matching policy clauses for both 'internal' and 'vendor' roles, and 
uses an LLM to compare them.

Generates a structured compliance delta: rag_findings and a compliance_matrix.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, cast

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from supabase import Client, create_client
from sentence_transformers import CrossEncoder

from state import VendorDueDiligenceState

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("comparator_agent")

# Configuration
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION: int = 384
TOP_K_FETCH: int = 20
TOP_K_PER_ROLE: int = 5
SIMILARITY_THRESHOLD: float = 0.0

DEFAULT_RAG_QUERY: str = "security data protection encryption access control vendor compliance"

_supabase_client: Client | None = None
_embedding_model: HuggingFaceEmbeddings | None = None

def _get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url: str | None = os.environ.get("SUPABASE_URL")
    key: str | None = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        log.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    _supabase_client = create_client(url, key)
    return _supabase_client

def _get_embedding_model() -> HuggingFaceEmbeddings:
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    _embedding_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return _embedding_model


_cross_encoder: CrossEncoder | None = None

def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is not None:
        return _cross_encoder
    log.info("Loading local Cross-Encoder model: cross-encoder/ms-marco-MiniLM-L-6-v2 ...")
    _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
    return _cross_encoder


def _rewrite_query(vendor: str) -> str:
    """Uses an LLM to expand the static query into an optimized Hybrid Search query."""
    prompt = f"We are auditing the vendor '{vendor}'. Expand the following base topics into a highly descriptive search query containing relevant cybersecurity keywords, acronyms, and synonyms for retrieving policies. Base topics: {DEFAULT_RAG_QUERY}. Output only the query string without quotes or preamble."
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    try:
        response = llm.invoke(prompt)
        rewritten = response.content.strip()
        log.info("Query rewritten via LLM: %s", rewritten)
        return rewritten
    except Exception as e:
        log.warning("Query rewriting failed: %s. Falling back to default query.", e)
        return DEFAULT_RAG_QUERY

def _retrieve_chunks(query_text: str, user_id: str) -> list[tuple[Document, float]]:
    db: Client = _get_supabase_client()
    model: HuggingFaceEmbeddings = _get_embedding_model()

    query_vector: list[float] = model.embed_query(query_text)

    try:
        response = (
            db.rpc(
                "hybrid_search_document_chunks",
                {
                    "query_text": query_text,
                    "query_embedding": query_vector,
                    "p_user_id": user_id,
                    "match_count": TOP_K_FETCH,
                },
            ).execute()
        )
    except Exception as exc:
        log.error("Supabase hybrid search failed: %s", exc)
        return []

    rows: list[dict[str, Any]] = cast(
        list[dict[str, Any]],
        response.data if response.data else [],
    )

    results: list[tuple[Document, float]] = []
    for row in rows:
        db_metadata = row.get("metadata") or {}
        role = db_metadata.get("role", "unknown")
        
        doc = Document(
            page_content=str(row.get("content", "")),
            metadata={
                "document_id": str(row.get("document_id", "")),
                "similarity":  float(row.get("similarity", 0.0)),
                "role": role,
            },
        )
        results.append((doc, float(row.get("similarity", 0.0))))

    return results

def _fetch_parent_context(db: Client, document_id: str) -> tuple[str, bool]:
    if not document_id:
        return ("", True)
    try:
        response = db.table("documents").select("content").eq("id", document_id).limit(1).execute()
        rows: list[dict[str, Any]] = cast(list[dict[str, Any]], response.data if response.data else [])
        if rows:
            content: str = str(rows[0].get("content", ""))
            if content:
                return (content, False)
        return ("", True)
    except Exception as exc:
        return (f"(parent lookup failed: {exc})", False)

class ComplianceAnalysis(BaseModel):
    findings: list[str] = Field(description="List of specific discrepancies and policy gaps identified")
    matrix: dict[str, Any] = Field(description="Structured dictionary mapping compliance categories (e.g., 'Encryption', 'Access Control') to their status and details")

def run_policy_comparison(vendor: str, internal_text: str, vendor_text: str) -> tuple[list[str], dict]:
    """
    Runs only the LLM comparison step of the comparator pipeline.
    Reusable by both the main pipeline and the Policy Sandbox.
    Returns (findings, compliance_matrix).
    """
    prompt = f"""
You are a Lead Security Architect performing Vendor Due Diligence for {vendor}.
Compare the following Internal Policies against the Vendor's Policies.

INTERNAL POLICIES:
{internal_text if internal_text else "None provided."}

VENDOR POLICIES:
{vendor_text if vendor_text else "None provided."}

Extract specific discrepancies where the vendor fails to meet internal requirements, and generate a structured compliance matrix.
"""
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, timeout=60, max_retries=2)
    structured_llm = llm.with_structured_output(ComplianceAnalysis)

    try:
        analysis: ComplianceAnalysis = structured_llm.invoke(prompt)
        return analysis.findings, analysis.matrix
    except Exception as e:
        log.error("LLM policy comparison failed: %s", e)
        return [f"Failed to analyze policies: {e}"], {}

def comparator_agent_node(state: VendorDueDiligenceState) -> dict:
    """
    Comparator agent node for the LangGraph pipeline.
    """
    vendor: str = state.get("vendor_name", "unknown vendor")
    user_id: str = state.get("user_id", "")
    
    log.info("Comparator Agent activated for vendor: %s", vendor)
    
    # 1. Query Rewriting
    rewritten_query = _rewrite_query(vendor)
    
    # 2. Hybrid Search + RRF
    hybrid_results = _retrieve_chunks(rewritten_query, user_id)
    
    if not hybrid_results:
        log.warning("No matching chunks found for comparison.")
        return {
            "rag_findings": ["No policy documents found for comparison."],
            "compliance_matrix": {},
        }
        
    # 3. Cross-Encoder Reranking
    cross_encoder = _get_cross_encoder()
    pairs = [[rewritten_query, doc.page_content] for doc, _ in hybrid_results]
    try:
        scores = cross_encoder.predict(pairs)
        # Sort documents by their cross-encoder score descending
        results = [
            (doc, float(score)) 
            for score, (doc, _) in sorted(zip(scores, hybrid_results), key=lambda x: x[0], reverse=True)
        ]
        log.info("Successfully reranked %d chunks via Cross-Encoder.", len(results))
    except Exception as e:
        log.error("Cross-Encoder reranking failed: %s. Falling back to DB RRF rankings.", e)
        results = hybrid_results

    db: Client = _get_supabase_client()
    
    # Separate by role
    internal_candidates = [item for item in results if item[0].metadata.get("role") == "internal"]
    vendor_candidates = [item for item in results if item[0].metadata.get("role", "unknown") == "vendor"]

    def apply_mmr(candidates, k):
        if not candidates:
            return []
        if len(candidates) <= k:
            return [doc for doc, _ in candidates]
            
        model = _get_embedding_model()
        docs_text = [c[0].page_content for c in candidates]
        embeddings = np.array(model.embed_documents(docs_text))
        scores = [c[1] for c in candidates]
        
        max_s = max(scores)
        min_s = min(scores)
        norm_scores = [(s - min_s) / (max_s - min_s) if max_s > min_s else 1.0 for s in scores]
            
        selected = []
        unselected = list(range(len(candidates)))
        
        first_idx = int(np.argmax(norm_scores))
        selected.append(first_idx)
        unselected.remove(first_idx)
        
        while len(selected) < k and unselected:
            best_score = -float("inf")
            best_idx = -1
            selected_emb = embeddings[selected]
            
            for idx in unselected:
                emb = embeddings[idx:idx+1]
                max_sim = np.max(cosine_similarity(emb, selected_emb)[0])
                mmr_score = 0.5 * norm_scores[idx] - 0.5 * max_sim
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            selected.append(best_idx)
            unselected.remove(best_idx)
            
        return [candidates[i][0] for i in selected]

    final_internal_docs = apply_mmr(internal_candidates, TOP_K_PER_ROLE)
    final_vendor_docs = apply_mmr(vendor_candidates, TOP_K_PER_ROLE)

    internal_docs = []
    vendor_docs = []
    raw_rag_clauses = []
    
    for doc in final_internal_docs:
        parent_text, is_orphan = _fetch_parent_context(db, str(doc.metadata.get("document_id", "")))
        clause = doc.page_content
        source = doc.metadata.get("source", "Internal Policy")
        final_text = parent_text if parent_text and not is_orphan else clause

        # Sanitize before it reaches any LLM prompt
        clean_text = sanitize_text(final_text, source_label=source)
        if not clean_text:
            continue

        internal_docs.append(clean_text)
        raw_rag_clauses.append({
            "clause_text": clause,
            "parent_context": clean_text,
            "role": "internal",
            "source": source
        })
        
    for doc in final_vendor_docs:
        parent_text, is_orphan = _fetch_parent_context(db, str(doc.metadata.get("document_id", "")))
        clause = doc.page_content
        source = doc.metadata.get("source", "Vendor Policy")
        final_text = parent_text if parent_text and not is_orphan else clause

        # Sanitize before it reaches any LLM prompt
        clean_text = sanitize_text(final_text, source_label=source)
        if not clean_text:
            continue

        vendor_docs.append(clean_text)
        raw_rag_clauses.append({
            "clause_text": clause,
            "parent_context": clean_text,
            "role": "vendor",
            "source": source
        })

    internal_text = "\n\n---\n\n".join(internal_docs)
    vendor_text = "\n\n---\n\n".join(vendor_docs)

    findings, matrix = run_policy_comparison(vendor, internal_text, vendor_text)
    log.info(f"Comparator found {len(findings)} discrepancies.")
    
    return {
        "rag_findings": findings,
        "compliance_matrix": matrix,
        "raw_rag_clauses": raw_rag_clauses,
    }
