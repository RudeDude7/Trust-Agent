"""
ingest.py — Hierarchical RAG Ingestion Pipeline (Zero-Cost Edition)

Loads a PDF, splits it into parent/child chunks, generates embeddings
locally on your machine (free), and inserts everything into Supabase.

Prerequisites (run once):
    pip install sentence-transformers langchain-huggingface

Usage:
    python ingest.py
    python ingest.py --pdf path/to/your/file.pdf
"""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
import os

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import Client, create_client

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_PDF: Path = Path(__file__).parent / "sample_policy.pdf"
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION: int = 384            # must match VECTOR(384) in schema.sql
BATCH_SIZE: int = 50                      # rows per Supabase insert call


# ---------------------------------------------------------------------------
# Splitter setup (mirrors test_chunking.py for consistency)
# ---------------------------------------------------------------------------
PARENT_SPLITTER: RecursiveCharacterTextSplitter = (
    RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=1000,
        chunk_overlap=100,
    )
)

CHILD_SPLITTER: RecursiveCharacterTextSplitter = (
    RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=200,
        chunk_overlap=20,
    )
)


# ---------------------------------------------------------------------------
# Initialization helpers
# ---------------------------------------------------------------------------
def get_supabase_client() -> Client:
    """Creates an authenticated Supabase client from env vars."""
    url: str | None = os.environ.get("SUPABASE_URL")
    key: str | None = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        log.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    client: Client = create_client(url, key)
    log.info("Supabase client connected → %s", url.split("//")[1][:25] + "…")
    return client


def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Loads the sentence-transformer model into memory.
    First run downloads ~80 MB; subsequent runs use the cached copy.
    """
    log.info("Loading local embedding model: %s …", EMBEDDING_MODEL)
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},      # safe default for MacBook Air
        encode_kwargs={"normalize_embeddings": True},
    )
    log.info("Embedding model ready (dimension=%d).", EMBEDDING_DIMENSION)
    return embeddings


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
def load_pdf(pdf_path: Path) -> list[Document]:
    """Stage 1: Load raw pages from the PDF."""
    if not pdf_path.exists():
        log.error("PDF not found: %s", pdf_path)
        sys.exit(1)

    loader = PyMuPDFLoader(str(pdf_path))
    pages: list[Document] = loader.load()
    log.info("Loaded %d raw pages from %s", len(pages), pdf_path.name)
    return pages


def build_chunk_hierarchy(pages: list[Document]) -> list[dict]:
    """
    Stage 2: Split pages → parents → children.

    Returns a list of parent records, each carrying its own children:
        [
            {
                "parent_id": "uuid-...",
                "content":   "...",
                "metadata":  {...},
                "children":  [{"content": "...", "metadata": {...}}, ...]
            },
            ...
        ]
    """
    parents: list[Document] = PARENT_SPLITTER.split_documents(pages)
    log.info("Created %d parent chunks (≈1 000 tokens each).", len(parents))

    hierarchy: list[dict] = []

    for parent_doc in parents:
        parent_id: str = str(uuid.uuid4())

        children: list[Document] = CHILD_SPLITTER.split_documents([parent_doc])

        hierarchy.append({
            "parent_id": parent_id,
            "content":   parent_doc.page_content,
            "metadata":  parent_doc.metadata,
            "children":  [
                {
                    "content":  child.page_content,
                    "metadata": child.metadata,
                }
                for child in children
            ],
        })

    total_children: int = sum(len(p["children"]) for p in hierarchy)
    log.info(
        "Created %d child chunks (≈200 tokens each).  Avg %.1f children/parent.",
        total_children,
        total_children / max(len(hierarchy), 1),
    )
    return hierarchy


def generate_child_embeddings(
    hierarchy: list[dict],
    model: HuggingFaceEmbeddings,
) -> None:
    """
    Stage 3: Generate embeddings for every child chunk in-place.

    Batches all child texts into a single call for efficiency — the
    sentence-transformer model handles batching internally on CPU.
    """
    all_texts: list[str] = []
    index_map: list[tuple[int, int]] = []   # (parent_idx, child_idx)

    for p_idx, parent in enumerate(hierarchy):
        for c_idx, child in enumerate(parent["children"]):
            all_texts.append(child["content"])
            index_map.append((p_idx, c_idx))

    log.info("Generating %d embeddings locally (this may take a moment) …", len(all_texts))
    vectors: list[list[float]] = model.embed_documents(all_texts)
    log.info("Embeddings generated successfully.")

    # Write vectors back into the hierarchy structure.
    for (p_idx, c_idx), vector in zip(index_map, vectors):
        hierarchy[p_idx]["children"][c_idx]["embedding"] = vector


def insert_into_supabase(
    hierarchy: list[dict],
    db: Client,
) -> None:
    """
    Stage 4: Insert parents and children into Supabase.

    Insertion order matters — parents first (FK target), then children.
    Uses batched upserts to stay within Supabase's request-size limits.
    """
    # --- Insert parent documents ---
    parent_rows: list[dict] = [
        {
            "id":       p["parent_id"],
            "content":  p["content"],
            "metadata": json.loads(json.dumps(p["metadata"], default=str)),
        }
        for p in hierarchy
    ]

    log.info("Inserting %d parent documents …", len(parent_rows))
    for i in range(0, len(parent_rows), BATCH_SIZE):
        batch = parent_rows[i : i + BATCH_SIZE]
        db.table("documents").insert(batch).execute()
        log.info("  ↳ parents batch %d–%d inserted.", i + 1, i + len(batch))

    # --- Insert child chunks (with embeddings) ---
    child_rows: list[dict] = []
    for parent in hierarchy:
        for child in parent["children"]:
            child_rows.append({
                "document_id": parent["parent_id"],
                "content":     child["content"],
                "embedding":   child["embedding"],
                "metadata":    json.loads(json.dumps(child["metadata"], default=str)),
            })

    log.info("Inserting %d child chunks …", len(child_rows))
    for i in range(0, len(child_rows), BATCH_SIZE):
        batch = child_rows[i : i + BATCH_SIZE]
        db.table("document_chunks").insert(batch).execute()
        log.info("  ↳ children batch %d–%d inserted.", i + 1, i + len(batch))

    log.info("✅  Ingestion complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trust Agent — Hierarchical RAG Ingestion (Zero-Cost)",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help="Path to the PDF to ingest (default: sample_policy.pdf)",
    )
    args = parser.parse_args()

    log.info("=" * 56)
    log.info("  Trust Agent — Ingestion Pipeline")
    log.info("=" * 56)

    # 1. Connect to infrastructure.
    db: Client = get_supabase_client()
    embedding_model: HuggingFaceEmbeddings = get_embedding_model()

    # 2. Load → Split → Embed → Insert.
    pages: list[Document] = load_pdf(args.pdf)
    hierarchy: list[dict] = build_chunk_hierarchy(pages)
    generate_child_embeddings(hierarchy, embedding_model)
    insert_into_supabase(hierarchy, db)


if __name__ == "__main__":
    main()


# ============================================================
# 🧠 Mentor Notes: The Zero-Cost RAG Strategy
# ============================================================
#
# Why local embeddings are a game-changer for bootstrapped projects:
#
# ┌────────────────────────┬──────────────────┬──────────────────┐
# │                        │  Cloud API       │  Local Model     │
# │                        │  (e.g. OpenAI)   │  (MiniLM-L6-v2)  │
# ├────────────────────────┼──────────────────┼──────────────────┤
# │ Cost per 1M tokens     │  ~$0.10–$0.13    │  $0.00           │
# │ Cost for 10K documents │  ~$1–$5          │  $0.00           │
# │ Cost for dev iteration │  Adds up fast    │  Always free     │
# │ Latency                │  Network-bound   │  CPU-bound       │
# │ Privacy                │  Data leaves     │  Data stays      │
# │                        │  your machine    │  on your machine │
# │ Offline dev            │  ✗ Needs WiFi    │  ✓ Works offline │
# │ Quality (MTEB avg)     │  ~63 (ada-002)   │  ~59 (MiniLM)    │
# └────────────────────────┴──────────────────┴──────────────────┘
#
# Key takeaways:
#
# 1. ITERATION COST IS THE REAL KILLER.
#    During development you re-ingest the same documents dozens of times
#    while tuning chunk sizes, overlap, metadata, and filtering logic.
#    With cloud APIs, every re-run costs real money.  With a local model,
#    you iterate freely — run it 100 times, pay $0.00.
#
# 2. THE QUALITY GAP IS SMALLER THAN YOU THINK.
#    all-MiniLM-L6-v2 scores ~59 on the MTEB benchmark vs ~63 for
#    OpenAI's ada-002.  For most retrieval tasks — especially when
#    combined with the Parent Document Retriever pattern — this gap
#    is negligible.  The architecture compensates.
#
# 3. DATA PRIVACY FOR FREE.
#    Your PDF contents never leave your MacBook.  No terms-of-service
#    to review, no data-processing agreements to sign.  For a vendor
#    risk tool handling sensitive company data, this matters.
#
# 4. THE UPGRADE PATH IS CLEAN.
#    If you later need higher-quality embeddings, swap the model name:
#        EMBEDDING_MODEL = "all-MiniLM-L6-v2"       # free, 384-d
#        EMBEDDING_MODEL = "all-mpnet-base-v2"       # free, 768-d, better quality
#    Or switch to a cloud provider by changing one class:
#        from langchain_google_genai import GoogleGenerativeAIEmbeddings
#    The rest of the pipeline stays identical.
#
# Bottom line: Use local embeddings while building.  Pay for cloud
# embeddings only when you've proven the product works and the quality
# delta actually matters for your users.
# ============================================================
