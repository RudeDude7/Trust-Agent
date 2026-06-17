-- ============================================================
-- Trust Agent: Hierarchical RAG Schema
-- Run this in your Supabase SQL Editor (in order, top to bottom).
-- ============================================================

-- 1. Enable the pgvector extension (required for vector storage).
--    Supabase ships pgvector but it must be explicitly enabled.
CREATE EXTENSION IF NOT EXISTS vector;


-- 2. Parent documents table.
--    Stores the larger, context-rich text chunks that are returned
--    to the LLM as grounding context after retrieval.
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content     TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE documents IS
    'Parent-level chunks (≈1000 tokens). Returned to the LLM as retrieval context.';


-- 3. Child chunks table.
--    Stores the smaller, semantically dense chunks whose embeddings
--    are compared against the user query during similarity search.
--    Each child references exactly one parent via document_id.
CREATE TABLE IF NOT EXISTS document_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content      TEXT        NOT NULL,
    embedding    VECTOR(384),          -- all-MiniLM-L6-v2 outputs 384-d vectors (free, local)
    metadata     JSONB       NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE document_chunks IS
    'Child-level chunks (≈200 tokens). Embeddings live here for similarity search.';


-- 4. Index for fast approximate nearest-neighbor search on embeddings.
--    HNSW is preferred over IVFFlat for most workloads: no training step,
--    better recall at comparable speed, and scales well under concurrent writes.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops);


-- 5. B-tree index on the foreign key for fast parent lookups after retrieval.
CREATE INDEX IF NOT EXISTS idx_chunks_document_id
    ON document_chunks (document_id);
