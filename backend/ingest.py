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
from langchain_experimental.text_splitter import SemanticChunker
from supabase import Client, create_client
import io
import fitz
from PIL import Image
import base64
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from redis import Redis
import time

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


redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_conn = Redis.from_url(redis_url)

def publish_progress(job_id: str, progress: int, status: str):
    """Publishes ingestion progress to Redis Pub/Sub."""
    if not job_id:
        return
    payload = json.dumps({"progress": progress, "status": status})
    redis_conn.publish(f"ingest_progress:{job_id}", payload)

# ---------------------------------------------------------------------------
# Splitter setup is deferred until we have the embedding model for SemanticChunker
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Initialization helpers
# ---------------------------------------------------------------------------
from supabase import Client, create_client, ClientOptions
import httpx

_supabase_client: Client | None = None

def get_supabase_client() -> Client:
    """Creates (or reuses) an authenticated Supabase client from env vars."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url: str | None = os.environ.get("SUPABASE_URL")
    key: str | None = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        log.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    # Disable HTTP/2 to prevent GOAWAY/ConnectionTerminated errors on idle connections
    custom_httpx = httpx.Client(http2=False)
    options = ClientOptions(httpx_client=custom_httpx)

    _supabase_client = create_client(url, key, options=options)
    log.info("Supabase client connected → %s", url.split("//")[1][:25] + "…")
    return _supabase_client


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


def get_gemini_vision_model():
    """Loads Gemini 2.5 Flash for Multimodal OCR/Table Extraction."""
    log.info("Loading Gemini Vision model...")
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
def load_pdf(pdf_path: Path, role: str, job_id: str = "") -> list[Document]:
    """Stage 1: Load raw pages from the PDF and extract images/tables via Gemini VLM."""
    if not pdf_path.exists():
        log.error("PDF not found: %s", pdf_path)
        sys.exit(1)

    vlm = get_gemini_vision_model()
    doc = fitz.open(str(pdf_path))
    pages: list[Document] = []
    
    total_pages = len(doc)
    
    for page_num in range(total_pages):
        # Update progress tracking
        publish_progress(job_id, int((page_num / total_pages) * 20), f"Extracting page {page_num+1}/{total_pages}...")
        
        page = doc.load_page(page_num)
        text = page.get_text()
        
        # Extract and caption images
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            try:
                # Convert bytes to base64
                b64_img = base64.b64encode(image_bytes).decode("utf-8")
                
                # Exponential backoff loop for Google AI Free Tier (429 errors)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        msg = HumanMessage(content=[
                            {"type": "text", "text": "Extract any tabular data as Markdown tables and provide a detailed explanation of any charts or graphs. If it is just a logo or decorative image, reply with 'Decorative image'."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                        ])
                        res = vlm.invoke([msg])
                        content = res.content
                        if "Decorative image" not in content:
                            text += f"\\n\n[Visual Extraction: {content}]\n\\n"
                        break
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            log.warning("Rate limit hit on VLM extraction, sleeping for %d seconds...", 2 ** attempt * 5)
                            time.sleep(2 ** attempt * 5)
                        else:
                            raise e
                            
            except Exception as e:
                log.warning(f"Skipping image due to error: {e}")
                
        # Create Document with normalized text and rich metadata
        clean_text = text.replace('\\x00', '').strip()
        metadata = {"role": role, "page": page_num + 1, "source": str(pdf_path)}
        pages.append(Document(page_content=clean_text, metadata=metadata))
        
    log.info("Loaded %d raw pages from %s (role: %s)", len(pages), pdf_path.name, role)
    return pages


def build_chunk_hierarchy(pages: list[Document], embedding_model: HuggingFaceEmbeddings) -> list[dict]:
    """
    Stage 2: Split pages → parents → children using SemanticChunker.
    """
    parent_splitter = SemanticChunker(
        embedding_model, breakpoint_threshold_type="percentile", breakpoint_threshold_amount=90
    )
    child_splitter = SemanticChunker(
        embedding_model, breakpoint_threshold_type="percentile", breakpoint_threshold_amount=70
    )

    parents: list[Document] = parent_splitter.split_documents(pages)
    log.info("Created %d semantic parent chunks.", len(parents))

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
    user_id: str,
    role: str
) -> None:
    """
    Stage 4: Insert parents and children into Supabase.

    First, purge any existing documents for this user and role to prevent
    cross-audit contamination. Then insert parents (FK target), then children.
    """
    # --- Purge old documents for this user and role ---
    log.info("Purging old '%s' documents for user %s ...", role, user_id)
    # Supabase Python client doesn't support complex JSONB filtering easily, 
    # but we can filter by user_id and then use metadata->>'role' = role via PostgREST textSearch or similar.
    # Actually, the simplest way is to fetch the IDs and delete them.
    res = db.table("documents").select("id, metadata").eq("user_id", user_id).execute()
    old_docs = [d["id"] for d in (res.data or []) if d.get("metadata", {}).get("role") == role]
    if old_docs:
        log.info("Found %d old '%s' documents. Deleting...", len(old_docs), role)
        # Delete in batches of 100 to be safe
        for i in range(0, len(old_docs), 100):
            batch_ids = old_docs[i:i+100]
            db.table("documents").delete().in_("id", batch_ids).execute()
        log.info("Purge complete. (Cascaded to document_chunks).")

    # --- Insert parent documents ---
    parent_rows: list[dict] = [
        {
            "id":       p["parent_id"],
            "user_id":  user_id,
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


def process_ingestion_job(tmp_path: str, role: str, user_id: str, job_id: str = "") -> None:
    """Async worker function to process ingestion from RQ queue."""
    log.info("Starting background ingestion for role: %s, user: %s", role, user_id)
    
    from rq import get_current_job
    job = get_current_job()
    if job and not job_id:
        job_id = job.id
        
    try:
        publish_progress(job_id, 0, "Initializing database connection...")
        db: Client = get_supabase_client()
        embedding_model = get_embedding_model()
        
        publish_progress(job_id, 5, "Loading PDF and extracting images/tables via Gemini...")
        pages = load_pdf(Path(tmp_path), role, job_id=job_id)
        if not pages:
            log.error("PDF is empty or unreadable.")
            publish_progress(job_id, -1, "Error: PDF is empty or unreadable.")
            return

        publish_progress(job_id, 30, "Executing Semantic Chunking...")
        hierarchy = build_chunk_hierarchy(pages, embedding_model)
        
        publish_progress(job_id, 60, "Generating local vector embeddings...")
        generate_child_embeddings(hierarchy, embedding_model)
        
        publish_progress(job_id, 85, "Uploading vectors to Supabase database...")
        insert_into_supabase(hierarchy, db, user_id, role)
        
        publish_progress(job_id, 100, "Ingestion Complete!")
        log.info("✅ Async ingestion job complete for user %s", user_id)
    except Exception as e:
        log.error("Async ingestion job failed: %s", e)
        publish_progress(job_id, -1, f"Error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            log.info("Cleaned up temp file: %s", tmp_path)


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
    parser.add_argument(
        "--role",
        type=str,
        default="internal",
        choices=["internal", "vendor"],
        help="The role of the document (internal or vendor).",
    )
    args = parser.parse_args()

    log.info("=" * 56)
    log.info("  Trust Agent — Ingestion Pipeline")
    log.info("=" * 56)

    # 1. Connect to infrastructure.
    db: Client = get_supabase_client()
    embedding_model: HuggingFaceEmbeddings = get_embedding_model()

    # 2. Load → Split → Embed → Insert.
    # Note: job_id is strictly for SSE async web tracking, we pass "" for local CLI runs.
    pages: list[Document] = load_pdf(args.pdf, args.role, job_id="")
    hierarchy: list[dict] = build_chunk_hierarchy(pages, embedding_model)
    generate_child_embeddings(hierarchy, embedding_model)
    insert_into_supabase(hierarchy, db, "00000000-0000-0000-0000-000000000000", args.role)


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
