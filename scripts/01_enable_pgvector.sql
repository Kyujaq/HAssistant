-- Enable pgvector extension for embedding search
-- This must run first before creating any tables that use VECTOR type

CREATE EXTENSION IF NOT EXISTS vector;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'pgvector extension enabled successfully';
END $$;
