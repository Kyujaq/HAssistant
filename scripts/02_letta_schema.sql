-- Letta Memory Schema
-- Core tables for Letta framework with architect-recommended structure

-- Table: memory_blocks
-- Central memory storage with tiered retention and embedding support
CREATE TABLE memory_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'preference', 'entity', 'event', 'conversation', 'knowledge'
    tier TEXT NOT NULL,  -- 'permanent', 'long_term', 'medium_term', 'short_term', 'session'
    confidence REAL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    tags TEXT[] DEFAULT '{}',
    source TEXT[] DEFAULT '{}',  -- ['ha_event', 'conversation', 'user_explicit', 'inferred']
    lineage TEXT[] DEFAULT '{}',  -- ['conversation_id', 'message_id'] for tracing origin
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    pin BOOLEAN DEFAULT FALSE,  -- Prevents automatic eviction
    meta JSONB DEFAULT '{}'  -- Flexible metadata storage
);

-- Table: memory_embeddings
-- Vector embeddings for semantic search
CREATE TABLE memory_embeddings (
    memory_id UUID REFERENCES memory_blocks(id) ON DELETE CASCADE,
    embedding VECTOR(384),  -- Matches all-MiniLM-L6-v2 dimension
    PRIMARY KEY (memory_id)
);

-- Table: agent_state
-- Letta agent state persistence
CREATE TABLE agent_state (
    agent_id TEXT PRIMARY KEY,
    state JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Trigger function for updating last_used_at on access
CREATE OR REPLACE FUNCTION update_memory_last_used()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_used_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to memory_blocks for access tracking
CREATE TRIGGER track_memory_access
    BEFORE UPDATE ON memory_blocks
    FOR EACH ROW
    WHEN (OLD.content = NEW.content AND OLD.last_used_at != NEW.last_used_at)
    EXECUTE FUNCTION update_memory_last_used();

-- Trigger function for updating agent_state timestamp
CREATE OR REPLACE FUNCTION update_agent_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to agent_state
CREATE TRIGGER update_agent_state_updated_at
    BEFORE UPDATE ON agent_state
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_state_timestamp();

-- Function: Memory eviction based on tier and last_used_at
-- Called by scheduled job or maintenance endpoint
CREATE OR REPLACE FUNCTION evict_old_memories()
RETURNS TABLE(evicted_count INTEGER, tier TEXT) AS $$
DECLARE
    session_cutoff TIMESTAMPTZ := CURRENT_TIMESTAMP - INTERVAL '1 hour';
    short_cutoff TIMESTAMPTZ := CURRENT_TIMESTAMP - INTERVAL '7 days';
    medium_cutoff TIMESTAMPTZ := CURRENT_TIMESTAMP - INTERVAL '30 days';
    long_cutoff TIMESTAMPTZ := CURRENT_TIMESTAMP - INTERVAL '365 days';
    session_deleted INTEGER;
    short_deleted INTEGER;
    medium_deleted INTEGER;
    long_deleted INTEGER;
BEGIN
    -- Evict session-tier memories older than 1 hour
    DELETE FROM memory_blocks
    WHERE tier = 'session'
      AND last_used_at < session_cutoff
      AND pin = FALSE;
    GET DIAGNOSTICS session_deleted = ROW_COUNT;

    -- Evict short-term memories older than 7 days
    DELETE FROM memory_blocks
    WHERE tier = 'short_term'
      AND last_used_at < short_cutoff
      AND pin = FALSE;
    GET DIAGNOSTICS short_deleted = ROW_COUNT;

    -- Evict medium-term memories older than 30 days
    DELETE FROM memory_blocks
    WHERE tier = 'medium_term'
      AND last_used_at < medium_cutoff
      AND pin = FALSE;
    GET DIAGNOSTICS medium_deleted = ROW_COUNT;

    -- Evict long-term memories older than 365 days
    DELETE FROM memory_blocks
    WHERE tier = 'long_term'
      AND last_used_at < long_cutoff
      AND pin = FALSE;
    GET DIAGNOSTICS long_deleted = ROW_COUNT;

    -- Return eviction summary
    RETURN QUERY
    SELECT session_deleted, 'session'::TEXT
    UNION ALL SELECT short_deleted, 'short_term'::TEXT
    UNION ALL SELECT medium_deleted, 'medium_term'::TEXT
    UNION ALL SELECT long_deleted, 'long_term'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Function: Promote memory tier (e.g., short_term → permanent)
CREATE OR REPLACE FUNCTION promote_memory_tier(
    memory_uuid UUID,
    new_tier TEXT
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE memory_blocks
    SET tier = new_tier,
        last_used_at = CURRENT_TIMESTAMP
    WHERE id = memory_uuid;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function: Pin/Unpin memory (for HA UI buttons)
CREATE OR REPLACE FUNCTION toggle_memory_pin(
    memory_uuid UUID,
    should_pin BOOLEAN
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE memory_blocks
    SET pin = should_pin,
        last_used_at = CURRENT_TIMESTAMP
    WHERE id = memory_uuid;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions to hassistant user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hassistant;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hassistant;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO hassistant;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Letta memory schema initialized successfully';
    RAISE NOTICE 'Tables created: memory_blocks, memory_embeddings, agent_state';
    RAISE NOTICE 'Helper functions: evict_old_memories(), promote_memory_tier(), toggle_memory_pin()';
END $$;