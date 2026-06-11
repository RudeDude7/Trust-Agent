"""
test_chunking.py — Verifies the parent/child split logic before any DB or embedding work.

Usage:
    1. Place a file named `sample_policy.pdf` in this directory.
    2. Run:  python test_chunking.py
"""

import sys
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PDF_PATH: Path = Path(__file__).parent / "sample_policy.pdf"

# Token-aware splitters that mirror what ParentDocumentRetriever uses internally.
# from_tiktoken_encoder counts real tokens (cl100k_base) instead of characters,
# so "200 tokens" actually means ≈200 tokens, not ≈200 characters.
PARENT_SPLITTER: RecursiveCharacterTextSplitter = (
    RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=1000,       # ≈1 000 tokens per parent chunk
        chunk_overlap=100,     # slight overlap to preserve boundary context
    )
)

CHILD_SPLITTER: RecursiveCharacterTextSplitter = (
    RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=200,        # ≈200 tokens per child chunk
        chunk_overlap=20,
    )
)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def load_pdf(path: Path) -> list[Document]:
    """Loads a PDF via PyMuPDF and returns one Document per page."""
    loader = PyMuPDFLoader(str(path))
    pages: list[Document] = loader.load()
    return pages


def split_into_parents(pages: list[Document]) -> list[Document]:
    """Splits raw pages into larger parent chunks (≈1 000 tokens)."""
    return PARENT_SPLITTER.split_documents(pages)


def split_into_children(parents: list[Document]) -> list[Document]:
    """Splits each parent chunk into smaller child chunks (≈200 tokens)."""
    return CHILD_SPLITTER.split_documents(parents)


def print_diagnostics(
    pages: list[Document],
    parents: list[Document],
    children: list[Document],
) -> None:
    """Prints a clear summary of the chunking pipeline."""
    print("=" * 56)
    print("  Trust Agent — Chunking Diagnostic Report")
    print("=" * 56)
    print(f"  Source PDF:          {PDF_PATH.name}")
    print(f"  Raw pages loaded:    {len(pages)}")
    print(f"  Parent chunks:       {len(parents)}   (≈1 000 tokens each)")
    print(f"  Child chunks:        {len(children)}   (≈200 tokens each)")
    print(f"  Avg children/parent: {len(children) / max(len(parents), 1):.1f}")
    print("=" * 56)

    # Preview the first parent and its first child so you can eyeball quality.
    if parents:
        preview = parents[0].page_content[:300].replace("\n", " ")
        print(f"\n📄 First parent chunk (preview):\n   \"{preview}...\"\n")
    if children:
        preview = children[0].page_content[:200].replace("\n", " ")
        print(f"🧩 First child chunk  (preview):\n   \"{preview}...\"\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if not PDF_PATH.exists():
        print(f"[Error] PDF not found at: {PDF_PATH}")
        print("        Place a file named 'sample_policy.pdf' in the project root.")
        sys.exit(1)

    pages: list[Document] = load_pdf(PDF_PATH)
    parents: list[Document] = split_into_parents(pages)
    children: list[Document] = split_into_children(parents)

    print_diagnostics(pages, parents, children)


if __name__ == "__main__":
    main()


# ============================================================
# 🧠 Mentor Notes — Why Two Tables?
# ============================================================
#
# In a standard (flat) RAG system you embed and retrieve the SAME chunk.
# That forces a painful trade-off:
#
#   • Small chunks (≈200 tokens) → great embedding precision,
#     but the LLM receives tiny, context-starved snippets.
#
#   • Large chunks (≈1 000 tokens) → the LLM gets rich context,
#     but the embedding is a diluted average of too many ideas,
#     so similarity search becomes noisier.
#
# The Parent Document Retriever eliminates this trade-off by
# DECOUPLING retrieval from grounding:
#
#   1. SEARCH happens on the small child chunks (document_chunks table).
#      Their embeddings are tight and semantically focused, so cosine
#      similarity gives you the most relevant hits.
#
#   2. GROUNDING happens on the parent chunks (documents table).
#      Once you find the best child, you follow the foreign key
#      (document_id) back to the parent and send THAT larger chunk
#      to the LLM.  The model now sees surrounding context — headings,
#      qualifiers, adjacent clauses — that a 200-token fragment would
#      have lost.
#
# That's why the SQL schema has two tables with a FK relationship:
#
#   documents  ←──  document_chunks
#   (grounding)     (search / embeddings)
#
# Think of it like a book index:
#   • The INDEX entries (child chunks) help you find the right page fast.
#   • But you read the full PAGE (parent chunk), not the index entry.
#
# This architecture gives you the best of both worlds:
#   ✓  High retrieval precision (small, dense embeddings)
#   ✓  High answer quality     (large, context-rich grounding)
# ============================================================
