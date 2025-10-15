-- Memory Deduplication and Performance Enhancements
-- Step 2.5: Memory ↔ LLM Integration
-- This migration adds hash-based deduplication and performance indexes

-- Add deduplication and auditing columns
ALTER TABLE IF EXISTS memories
  ADD COLUMN IF NOT EXISTS hash_id text,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- Backfill hash_id for existing records (normalized lowercase hash)
UPDATE memories
SET hash_id = substring(encode(sha256(lower(trim(text))::bytea), 'hex'), 1, 16)
WHERE hash_id IS NULL;

-- Make hash_id required and unique going forward
ALTER TABLE memories
  ALTER COLUMN hash_id SET NOT NULL,
  ADD CONSTRAINT memories_hash_id_unique UNIQUE (hash_id);

-- Performance indexes for filtered search and recency queries
CREATE INDEX IF NOT EXISTS ix_memories_kind_created
  ON memories(kind, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_memories_hash
  ON memories(hash_id);

-- Index for role filtering (meta JSONB field)
-- This enables fast queries like: WHERE meta->>'role' = 'user'
CREATE INDEX IF NOT EXISTS ix_mem_meta_role
  ON memories ((meta->>'role'));

-- Index for turn_id traceability
CREATE INDEX IF NOT EXISTS ix_mem_meta_turn_id
  ON memories ((meta->>'turn_id'));

-- Add updated_at trigger for automatic timestamp management
CREATE OR REPLACE FUNCTION update_memories_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS memories_updated_at_trigger ON memories;
CREATE TRIGGER memories_updated_at_trigger
  BEFORE UPDATE ON memories
  FOR EACH ROW
  EXECUTE FUNCTION update_memories_updated_at();

-- Optimize vector search for larger datasets (run when > 10k rows)
-- Uncomment and adjust 'lists' parameter based on dataset size:
-- DROP INDEX IF EXISTS ix_embed_vec;
-- CREATE INDEX ix_embed_vec ON embeddings
--   USING ivfflat (vec vector_l2_ops) WITH (lists = 200);

-- Verify the migration
DO $$
BEGIN
  RAISE NOTICE 'Migration 05_memory_dedup.sql completed successfully';
  RAISE NOTICE 'Added columns: hash_id, updated_at';
  RAISE NOTICE 'Added indexes: kind_created, hash, meta_role, meta_turn_id';
  RAISE NOTICE 'Added trigger: updated_at auto-update';
END $$;
