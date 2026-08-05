-- ============================================================
-- Trust Agent: Phase 8 Migration (Hybrid Search & RRF)
-- ============================================================

-- Create a new function for Hybrid Search leveraging Reciprocal Rank Fusion (RRF).
-- This runs both Vector (HNSW) and Sparse (BM25) searches simultaneously,
-- ranks the results, and fuses them mathematically for supreme accuracy.

CREATE OR REPLACE FUNCTION hybrid_search_document_chunks(
    query_text TEXT,
    query_embedding VECTOR(384),
    p_user_id UUID,
    match_count INT DEFAULT 15,
    full_text_weight FLOAT DEFAULT 1.0,
    semantic_weight FLOAT DEFAULT 1.0,
    rrf_k INT DEFAULT 60
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
WITH fts_search AS (
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.metadata,
        ts_rank(dc.fts_lexemes, plainto_tsquery('english', query_text)) AS fts_rank,
        ROW_NUMBER() OVER (ORDER BY ts_rank(dc.fts_lexemes, plainto_tsquery('english', query_text)) DESC) AS rank_idx
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE dc.fts_lexemes @@ plainto_tsquery('english', query_text)
      AND d.user_id = p_user_id
    LIMIT 100
),
vector_search AS (
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.metadata,
        1 - (dc.embedding <=> query_embedding) AS semantic_rank,
        ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding) AS rank_idx
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE dc.embedding IS NOT NULL
      AND d.user_id = p_user_id
    LIMIT 100
),
rrf_fusion AS (
    SELECT
        COALESCE(f.id, v.id) AS id,
        COALESCE(f.document_id, v.document_id) AS document_id,
        COALESCE(f.content, v.content) AS content,
        COALESCE(f.metadata, v.metadata) AS metadata,
        (
            full_text_weight * (1.0 / (rrf_k + COALESCE(f.rank_idx, 1000)))
        ) + (
            semantic_weight * (1.0 / (rrf_k + COALESCE(v.rank_idx, 1000)))
        ) AS similarity
    FROM fts_search f
    FULL OUTER JOIN vector_search v ON f.id = v.id
)
SELECT id, document_id, content, metadata, similarity
FROM rrf_fusion
ORDER BY similarity DESC
LIMIT match_count;
$$;

COMMENT ON FUNCTION hybrid_search_document_chunks IS
    'Multi-stage retrieval RPC. Executes parallel BM25 and Vector search, returning RRF-fused rankings filtered by tenant ID.';
