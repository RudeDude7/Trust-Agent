-- ============================================================
-- Trust Agent: Phase 6 Migration (RAG Multi-Tenancy Fix)
-- ============================================================

-- 1. Add user_id to documents
-- We add the column and allow NULL temporarily if there are existing rows,
-- then we could backfill or just delete them. Since this is for isolation,
-- let's delete existing global documents (they are orphan policies now).
DELETE FROM documents;
ALTER TABLE documents ADD COLUMN user_id UUID NOT NULL;

-- 2. Drop and recreate match_document_chunks to filter by user_id
DROP FUNCTION IF EXISTS match_document_chunks(VECTOR(384), INT, FLOAT);

CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding  VECTOR(384),
    p_user_id        UUID,
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
    JOIN documents d ON dc.document_id = d.id
    WHERE d.user_id = p_user_id
      AND dc.embedding IS NOT NULL
      AND 1 - (dc.embedding <=> query_embedding) >= match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
$$;

COMMENT ON FUNCTION match_document_chunks IS
    'Vector similarity search used by rag_agent.py. Filters by user_id for multi-tenant isolation.';
