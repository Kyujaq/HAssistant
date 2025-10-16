CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
  id UUID PRIMARY KEY,
  kind TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source TEXT NOT NULL,
  text TEXT NOT NULL,
  meta JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS embeddings (
  memory_id UUID PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
  vec VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_memories_kind_created ON memories(kind, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_embed_vec ON embeddings USING ivfflat (vec vector_l2_ops) WITH (lists = 100);
