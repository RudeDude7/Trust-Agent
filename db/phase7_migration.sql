-- ============================================================
-- Phase 1 Ingestion: Dual Vector / Sparse Indexing Migration
-- Adds tsvector column and trigger to automatically populate
-- full-text search lexemes from the chunk content.
-- ============================================================

-- 1. Add the tsvector column for sparse (BM25) indexing
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS fts_lexemes tsvector;

-- 2. Create a GIN index for fast text search
CREATE INDEX IF NOT EXISTS idx_chunks_fts_lexemes
ON document_chunks USING GIN (fts_lexemes);

-- 3. Create a function to automatically update the tsvector
CREATE OR REPLACE FUNCTION generate_fts_lexemes()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fts_lexemes = to_tsvector('english', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. Create the trigger to fire on INSERT and UPDATE
DROP TRIGGER IF EXISTS trigger_generate_fts_lexemes ON document_chunks;
CREATE TRIGGER trigger_generate_fts_lexemes
BEFORE INSERT OR UPDATE OF content
ON document_chunks
FOR EACH ROW
EXECUTE FUNCTION generate_fts_lexemes();

-- 5. Backfill existing data
UPDATE document_chunks
SET fts_lexemes = to_tsvector('english', content)
WHERE fts_lexemes IS NULL;
