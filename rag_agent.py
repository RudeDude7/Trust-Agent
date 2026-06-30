"""
rag_agent.py — RAG Agent Node for the Vendor Due Diligence Pipeline

Performs vector similarity search against the Supabase document_chunks table,
retrieves matching policy clauses, and maps them into the RAGClause format
defined in state.py.

Uses the same local HuggingFace embedding model (all-MiniLM-L6-v2) as
ingest.py to ensure query embeddings live in the same vector space as the
stored document embeddings.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, cast

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from supabase import Client, create_client

from state import RAGClause, VendorDueDiligenceState

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rag_agent")


# ---------------------------------------------------------------------------
# Configuration — must match ingest.py and schema.sql
# ---------------------------------------------------------------------------
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION: int = 384
TOP_K: int = 3                            # number of child chunks to retrieve
SIMILARITY_THRESHOLD: float = 0.0         # minimum cosine similarity (0 = return all)

# Default query when the state doesn't supply one yet.
DEFAULT_RAG_QUERY: str = "data encryption policy vendor compliance"


# ---------------------------------------------------------------------------
# Singleton-style caches (avoid re-initializing on every graph invocation)
# ---------------------------------------------------------------------------
_supabase_client: Client | None = None
_embedding_model: HuggingFaceEmbeddings | None = None


def _get_supabase_client() -> Client:
    """Returns a cached Supabase client, creating it on first call."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url: str | None = os.environ.get("SUPABASE_URL")
    key: str | None = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        log.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    _supabase_client = create_client(url, key)
    log.info("Supabase client connected → %s", url.split("//")[1][:25] + "…")
    return _supabase_client


def _get_embedding_model() -> HuggingFaceEmbeddings:
    """Returns a cached embedding model, loading it on first call."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    log.info("Loading local embedding model: %s …", EMBEDDING_MODEL)
    _embedding_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    log.info("Embedding model ready (dimension=%d).", EMBEDDING_DIMENSION)
    return _embedding_model


# ---------------------------------------------------------------------------
# Core retrieval logic
# ---------------------------------------------------------------------------
def _retrieve_chunks(query: str) -> list[tuple[Document, float]]:
    """
    Embeds the query locally, then performs a cosine similarity search
    against the document_chunks table via a Supabase RPC call.

    Returns a list of (Document, similarity_score) tuples sorted by
    descending similarity.
    """
    db: Client = _get_supabase_client()
    model: HuggingFaceEmbeddings = _get_embedding_model()

    # 1. Embed the query text into a 384-d vector using the local model.
    log.info("Embedding query: \"%s\"", query[:80])
    query_vector: list[float] = model.embed_query(query)

    # 2. Call Supabase RPC for vector similarity search.
    #    This requires a database function — see the SQL block below.
    try:
        response = (
            db.rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_vector,
                    "match_count": TOP_K,
                    "match_threshold": SIMILARITY_THRESHOLD,
                },
            ).execute()
        )
    except Exception as exc:
        log.error("Supabase vector search failed: %s", exc)
        return []

    rows: list[dict[str, Any]] = cast(
        list[dict[str, Any]],
        response.data if response.data else [],
    )
    log.info("Vector search returned %d results.", len(rows))

    # 3. Map raw rows into LangChain Document objects with scores.
    results: list[tuple[Document, float]] = []
    for row in rows:
        doc = Document(
            page_content=str(row.get("content", "")),
            metadata={
                "document_id": str(row.get("document_id", "")),
                "similarity":  float(row.get("similarity", 0.0)),
            },
        )
        results.append((doc, float(row.get("similarity", 0.0))))

    return results


def _fetch_parent_context(db: Client, document_id: str) -> tuple[str, bool]:
    """
    Follows the FK from a child chunk back to its parent document
    to retrieve the larger context window for LLM grounding.

    Returns:
        A tuple of (parent_text, is_orphan).
        - If the parent exists: (parent_content, False)
        - If the parent is missing: ("", True)
        - If the query errors: (error_message, False)
    """
    if not document_id:
        return ("", True)

    try:
        response = (
            db.table("documents")
            .select("content")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )
        rows: list[dict[str, Any]] = cast(
            list[dict[str, Any]],
            response.data if response.data else [],
        )

        if rows:
            content: str = str(rows[0].get("content", ""))
            if content:
                return (content, False)

        # Parent row is missing — this child chunk is orphaned.
        return ("", True)

    except Exception as exc:
        log.warning("Failed to fetch parent context for %s: %s", document_id, exc)
        return (f"(parent lookup failed: {exc})", False)


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------
def rag_agent_node(state: VendorDueDiligenceState) -> dict:
    """
    RAG agent node for the LangGraph vendor due diligence pipeline.

    1. Determines the search query (from state or default).
    2. Embeds the query and performs vector similarity search.
    3. For each matching child chunk, fetches the parent context.
    4. If a parent is missing (orphan), falls back to the child's own
       text and fires a CRITICAL log alert.
    5. Returns results mapped to RAGClause format for state accumulation.
    """
    # Determine query — use state's rag_query if set, otherwise default.
    query: str = state.get("rag_query", "") or DEFAULT_RAG_QUERY
    vendor: str = state.get("vendor_name", "unknown vendor")

    log.info("=" * 50)
    log.info("RAG Agent activated for vendor: %s", vendor)
    log.info("Search query: \"%s\"", query)
    log.info("=" * 50)

    # Retrieve matching child chunks with similarity scores.
    results: list[tuple[Document, float]] = _retrieve_chunks(query)

    if not results:
        log.warning("No matching chunks found. Returning empty clause list.")
        return {
            "rag_clauses": [],
            "rag_query":   query,
            "rag_summary": f"RAG search for '{query}' returned 0 results.",
        }

    # Fetch parent context for each child and build RAGClause list.
    db: Client = _get_supabase_client()
    clauses: list[RAGClause] = []
    orphan_count: int = 0

    for doc, score in results:
        document_id: str = str(doc.metadata.get("document_id", ""))

        # --- Safety Net: Level 2 (Fallback) + Level 3 (Alert) ---
        parent_text, is_orphan = _fetch_parent_context(db, document_id)

        if is_orphan:
            # Level 3: Fire a CRITICAL alert (simulates Slack notification).
            log.critical(
                "CRITICAL: Orphaned child chunk detected for document ID %s. "
                "Database re-ingestion required.",
                document_id,
            )
            orphan_count += 1

            # Level 2: Fall back to the child's own text so the LLM still
            # receives the specific clause and can generate an answer.
            parent_text = doc.page_content
            log.warning(
                "  ↳ Falling back to child text as parent context for ID %s.",
                document_id,
            )

        clause: RAGClause = {
            "clause_text":      doc.page_content,
            "source_document":  document_id,
            "similarity_score": round(score, 4),
            "parent_context":   parent_text,
        }
        clauses.append(clause)
        log.info(
            "  ↳ Matched chunk (score=%.4f): \"%s…\"",
            score,
            doc.page_content[:60],
        )

    summary: str = (
        f"RAG search for '{query}' returned {len(clauses)} matching policy "
        f"clauses (top similarity: {clauses[0]['similarity_score']:.4f})."
    )

    if orphan_count > 0:
        orphan_warning: str = (
            f" ⚠️ {orphan_count} orphaned chunk(s) detected — "
            f"used child text as fallback."
        )
        summary += orphan_warning
        log.warning(orphan_warning.strip())

    log.info(summary)

    return {
        "rag_clauses": clauses,
        "rag_query":   query,
        "rag_summary": summary,
    }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick smoke test — run the agent node with a minimal state.
    test_state: VendorDueDiligenceState = {  # type: ignore[typeddict-item]
        "vendor_name": "TikTok",
        "vendor_url":  "https://tiktok.com",
    }

    result: dict = rag_agent_node(test_state)

    print("\n" + "=" * 56)
    print("       RAG AGENT — STANDALONE TEST RESULTS")
    print("=" * 56)
    print(f"  Query used       : {result.get('rag_query')}")
    print(f"  Clauses returned : {len(result.get('rag_clauses', []))}")
    for i, clause in enumerate(result.get("rag_clauses", []), 1):
        print(f"\n  --- Clause {i} (score: {clause['similarity_score']}) ---")
        print(f"  Text:    {clause['clause_text'][:100]}…")
        print(f"  Parent:  {clause['parent_context'][:100]}…")
    print("=" * 56 + "\n")


# ============================================================
# 🧠 Mentor Notes: The Missing Parent Safety Net
# ============================================================
#
# An "orphaned child chunk" is a vector embedding in document_chunks
# whose parent row in the documents table has been deleted or was
# never inserted.  This is lethal in a hierarchical RAG system
# because the LLM receives a child match but has NO parent context
# to ground its answer — producing hallucinations or refusals.
#
# We defend against this with a 3-level safety net:
#
#
# LEVEL 1 — DATABASE CONSTRAINT (schema.sql)
# ──────────────────────────────────────────
#   document_id UUID NOT NULL
#       REFERENCES documents(id)
#       ON DELETE CASCADE
#
#   This is the ROOT FIX.  ON DELETE CASCADE means:
#
#     "If a parent row in `documents` is deleted, PostgreSQL
#      automatically deletes every child row in `document_chunks`
#      that references it."
#
#   Orphans become structurally impossible at the database level.
#   No amount of buggy Python code can create them because the
#   database engine itself enforces the rule on every DELETE.
#
#   Think of it like a building code vs. a smoke alarm:
#   - The FK constraint is the building code (prevents the fire).
#   - The Python fallback is the smoke alarm (catches the fire).
#   You want both, but the building code is what keeps you safe.
#
#
# LEVEL 2 — PYTHON FALLBACK (rag_agent.py: _fetch_parent_context)
# ───────────────────────────────────────────────────────────────
#   If the parent lookup returns empty, we don't crash or return
#   a useless "(parent context unavailable)" string.  Instead:
#
#       parent_text = doc.page_content  # use the child's own text
#
#   The LLM still receives the specific matched clause.  The answer
#   quality degrades slightly (no surrounding context), but the
#   pipeline keeps running and the user gets a response.
#
#
# LEVEL 3 — CRITICAL ALERT (rag_agent.py: rag_agent_node)
# ───────────────────────────────────────────────────────
#   In the same fallback block, we fire:
#
#       log.critical("CRITICAL: Orphaned child chunk detected ...")
#
#   In production you'd wire this to a Slack webhook, PagerDuty,
#   or an ops dashboard.  The alert tells the team:
#   "Something bypassed the FK constraint — investigate and
#    re-ingest the affected documents."
#
#
# WHY ALL THREE?
# ──────────────
#   • Level 1 prevents 99.9% of orphans.  But constraints can be
#     dropped by migration scripts, or data can be imported via
#     bulk COPY that skips FK checks.
#
#   • Level 2 ensures the user always gets a response, even in
#     the 0.1% edge case.
#
#   • Level 3 ensures the engineering team knows about it within
#     seconds, not weeks.
#
#   Defense in depth.  Each layer compensates for the one above it.
# ============================================================

