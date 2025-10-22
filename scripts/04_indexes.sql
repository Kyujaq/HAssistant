-- Performance Indexes for All Tables
-- Optimizes queries for memory search, filtering, and analytics

-- ============================================================================
-- MEMORY_BLOCKS INDEXES (Letta core table)
-- ============================================================================

-- GIN indexes for array and JSONB searches
CREATE INDEX idx_memory_blocks_tags ON memory_blocks USING gin(tags);
CREATE INDEX idx_memory_blocks_meta ON memory_blocks USING gin(meta);
CREATE INDEX idx_memory_blocks_source ON memory_blocks USING gin(source);
CREATE INDEX idx_memory_blocks_lineage ON memory_blocks USING gin(lineage);

-- btree indexes for filtering and sorting
CREATE INDEX idx_memory_blocks_tier ON memory_blocks(tier);
CREATE INDEX idx_memory_blocks_type ON memory_blocks(type);
CREATE INDEX idx_memory_blocks_created_at ON memory_blocks(created_at DESC);
CREATE INDEX idx_memory_blocks_last_used_at ON memory_blocks(last_used_at DESC);
CREATE INDEX idx_memory_blocks_pin ON memory_blocks(pin) WHERE pin = TRUE;
CREATE INDEX idx_memory_blocks_confidence ON memory_blocks(confidence DESC);

-- Composite indexes for common queries
CREATE INDEX idx_memory_blocks_type_tier ON memory_blocks(type, tier);
CREATE INDEX idx_memory_blocks_tier_last_used ON memory_blocks(tier, last_used_at DESC);
CREATE INDEX idx_memory_blocks_pin_tier ON memory_blocks(pin, tier) WHERE pin = FALSE;

-- Full-text search on title and content (optional, for keyword search)
CREATE INDEX idx_memory_blocks_title_fts ON memory_blocks USING gin(to_tsvector('english', title));
CREATE INDEX idx_memory_blocks_content_fts ON memory_blocks USING gin(to_tsvector('english', content));

-- ============================================================================
-- MEMORY_EMBEDDINGS INDEXES (Vector search)
-- ============================================================================

-- IVFFlat index for approximate nearest neighbor search
-- Lists parameter should be sqrt(total_rows), adjust as data grows
-- Using cosine distance (most common for embeddings)
CREATE INDEX idx_memory_embeddings_vector ON memory_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Optional: L2 distance index (if needed)
-- CREATE INDEX idx_memory_embeddings_vector_l2 ON memory_embeddings
-- USING ivfflat (embedding vector_l2_ops)
-- WITH (lists = 100);

-- ============================================================================
-- AGENT_STATE INDEXES
-- ============================================================================

CREATE INDEX idx_agent_state_updated_at ON agent_state(updated_at DESC);
CREATE INDEX idx_agent_state_state ON agent_state USING gin(state);

-- ============================================================================
-- CONVERSATIONS INDEXES (Legacy operational data)
-- ============================================================================

CREATE INDEX idx_conversations_session_id ON conversations(session_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp DESC);
CREATE INDEX idx_conversations_intent ON conversations(intent);
CREATE INDEX idx_conversations_metadata ON conversations USING gin(metadata);
CREATE INDEX idx_conversations_model_used ON conversations(model_used);

-- Composite indexes for analytics
CREATE INDEX idx_conversations_session_timestamp ON conversations(session_id, timestamp DESC);
CREATE INDEX idx_conversations_intent_timestamp ON conversations(intent, timestamp DESC);

-- ============================================================================
-- MESSAGES INDEXES
-- ============================================================================

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX idx_messages_role ON messages(role);
CREATE INDEX idx_messages_promoted ON messages(promoted_to_memory) WHERE promoted_to_memory IS NOT NULL;
CREATE INDEX idx_messages_metadata ON messages USING gin(metadata);

-- Composite for conversation retrieval
CREATE INDEX idx_messages_conversation_timestamp ON messages(conversation_id, timestamp ASC);

-- ============================================================================
-- USER_PREFERENCES INDEXES
-- ============================================================================

CREATE INDEX idx_user_preferences_key ON user_preferences(preference_key);
CREATE INDEX idx_user_preferences_type ON user_preferences(preference_type);
CREATE INDEX idx_user_preferences_active ON user_preferences(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_user_preferences_updated_at ON user_preferences(updated_at DESC);
CREATE INDEX idx_user_preferences_memory_block ON user_preferences(memory_block_id) WHERE memory_block_id IS NOT NULL;
CREATE INDEX idx_user_preferences_value ON user_preferences USING gin(preference_value);

-- ============================================================================
-- ENTITIES INDEXES
-- ============================================================================

CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(entity_name);
CREATE INDEX idx_entities_type_name ON entities(entity_type, entity_name);
CREATE INDEX idx_entities_updated_at ON entities(updated_at DESC);
CREATE INDEX idx_entities_last_referenced ON entities(last_referenced DESC);
CREATE INDEX idx_entities_memory_block ON entities(memory_block_id) WHERE memory_block_id IS NOT NULL;
CREATE INDEX idx_entities_data ON entities USING gin(entity_data);

-- ============================================================================
-- SESSION_ANALYTICS INDEXES
-- ============================================================================

CREATE INDEX idx_session_analytics_session_id ON session_analytics(session_id);
CREATE INDEX idx_session_analytics_start_time ON session_analytics(start_time DESC);
CREATE INDEX idx_session_analytics_end_time ON session_analytics(end_time DESC) WHERE end_time IS NOT NULL;
CREATE INDEX idx_session_analytics_primary_intent ON session_analytics(primary_intent);
CREATE INDEX idx_session_analytics_device_info ON session_analytics USING gin(device_info);

-- ============================================================================
-- ANALYZE TABLES
-- ============================================================================

-- Update statistics for query planner
ANALYZE memory_blocks;
ANALYZE memory_embeddings;
ANALYZE agent_state;
ANALYZE conversations;
ANALYZE messages;
ANALYZE user_preferences;
ANALYZE entities;
ANALYZE session_analytics;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Database indexes created successfully';
    RAISE NOTICE 'GIN indexes: tags, meta, source, lineage, metadata, preference_value, entity_data';
    RAISE NOTICE 'IVFFlat indexes: memory_embeddings (vector cosine search)';
    RAISE NOTICE 'btree indexes: tier, type, timestamps, pin, confidence';
    RAISE NOTICE 'Full-text search: title_fts, content_fts';
    RAISE NOTICE 'All tables analyzed for query optimization';
END $$;
