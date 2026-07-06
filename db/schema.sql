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


-- 6. RPC function for vector similarity search.
--    Called by rag_agent.py via: db.rpc("match_document_chunks", {...})
--    Computes cosine similarity in PostgreSQL and returns the top-k matches.
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding  VECTOR(384),
    match_count      INT DEFAULT 3,
    match_threshold  FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    id            UUID,
    document_id   UUID,
    content       TEXT,
    metadata      JSONB,
    similarity    FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.metadata,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    WHERE dc.embedding IS NOT NULL
      AND 1 - (dc.embedding <=> query_embedding) >= match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
$$;

COMMENT ON FUNCTION match_document_chunks IS
    'Vector similarity search used by rag_agent.py. Returns top-k child chunks by cosine similarity.';


-- ============================================================
-- 7. SAFETY NET: Enforce FK constraint on existing tables.
--    If you created document_chunks without the FK (or need to
--    verify it exists), run this block.  It's safe to run even
--    if the constraint already exists — it will simply report
--    "constraint already exists" and do nothing.
-- ============================================================

-- Drop-if-exists + re-add pattern (idempotent):
ALTER TABLE document_chunks
    DROP CONSTRAINT IF EXISTS document_chunks_document_id_fkey;

ALTER TABLE document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey
    FOREIGN KEY (document_id)
    REFERENCES documents(id)
    ON DELETE CASCADE;

COMMENT ON CONSTRAINT document_chunks_document_id_fkey ON document_chunks IS
    'Cascade-deletes child chunks when a parent document is removed. Prevents orphaned embeddings.';


-- 8. DIAGNOSTIC: Find any orphaned child chunks that slipped in
--    before the FK constraint was active.  Should return 0 rows.
SELECT dc.id AS orphaned_chunk_id, dc.document_id AS missing_parent_id
FROM document_chunks dc
LEFT JOIN documents d ON dc.document_id = d.id
WHERE d.id IS NULL;
