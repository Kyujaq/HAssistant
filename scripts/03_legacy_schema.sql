-- Legacy Schema for Backward Compatibility
-- Preserves existing /assistant endpoints and analytics
-- Implements dual-write strategy to memory_blocks

-- Table: conversations
-- Operational logs of conversation sessions
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    user_input TEXT NOT NULL,
    assistant_response TEXT,
    intent VARCHAR(100),
    model_used VARCHAR(100),
    response_time_ms INTEGER,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',

    -- Additional tracking fields
    user_ip VARCHAR(45),
    confidence_score REAL,
    tokens_used INTEGER,
    error_details TEXT
);

-- Table: messages
-- Individual messages within conversations (for lineage tracking)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    promoted_to_memory UUID REFERENCES memory_blocks(id) ON DELETE SET NULL,  -- Lineage link
    metadata JSONB DEFAULT '{}'
);

-- Table: user_preferences
-- User preferences with dual-write to memory_blocks
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    preference_key VARCHAR(255) UNIQUE NOT NULL,
    preference_value JSONB NOT NULL,
    preference_type VARCHAR(50) DEFAULT 'learned',  -- 'explicit', 'learned', 'inferred', 'system'
    confidence_score REAL DEFAULT 1.0,
    source VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Lifecycle management
    last_confirmed TIMESTAMPTZ,
    times_referenced INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,

    -- Link to memory_blocks for dual-write
    memory_block_id UUID REFERENCES memory_blocks(id) ON DELETE SET NULL
);

-- Table: entities
-- Named entities (people, places, things) with dual-write to memory_blocks
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- 'person', 'place', 'device', 'item'
    entity_name VARCHAR(255) NOT NULL,
    entity_data JSONB NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_referenced TIMESTAMPTZ,
    reference_count INTEGER DEFAULT 0,

    -- Link to memory_blocks for dual-write
    memory_block_id UUID REFERENCES memory_blocks(id) ON DELETE SET NULL,

    UNIQUE(entity_type, entity_name)
);

-- Table: session_analytics
-- Session-level metrics
CREATE TABLE session_analytics (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMPTZ,
    total_exchanges INTEGER DEFAULT 0,
    primary_intent VARCHAR(100),
    user_satisfaction_score REAL,
    session_duration_seconds INTEGER,
    device_info JSONB DEFAULT '{}',
    location_context VARCHAR(255),

    -- Quality metrics
    avg_response_time_ms REAL,
    error_count INTEGER DEFAULT 0,
    successful_tasks INTEGER DEFAULT 0,
    context_switches INTEGER DEFAULT 0
);

-- Trigger: Auto-update updated_at on user_preferences
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function: Dual-write user_preference to memory_blocks
-- Automatically syncs preferences to Letta memory system
CREATE OR REPLACE FUNCTION sync_preference_to_memory()
RETURNS TRIGGER AS $$
DECLARE
    mem_id UUID;
    tier_value TEXT;
BEGIN
    -- Determine tier based on preference_type
    tier_value := CASE NEW.preference_type
        WHEN 'system' THEN 'permanent'
        WHEN 'explicit' THEN 'permanent'
        WHEN 'learned' THEN 'long_term'
        WHEN 'inferred' THEN 'medium_term'
        ELSE 'short_term'
    END;

    -- Insert or update memory_block
    INSERT INTO memory_blocks (
        title,
        content,
        type,
        tier,
        confidence,
        tags,
        source,
        lineage,
        pin,
        meta
    ) VALUES (
        NEW.preference_key,
        NEW.preference_value::TEXT,
        'preference',
        tier_value,
        NEW.confidence_score,
        ARRAY[NEW.preference_type],
        ARRAY[COALESCE(NEW.source, 'user_preferences_table')],
        ARRAY['preference:' || NEW.id::TEXT],
        (NEW.preference_type IN ('system', 'explicit')),  -- Pin important preferences
        jsonb_build_object(
            'preference_id', NEW.id,
            'last_confirmed', NEW.last_confirmed,
            'times_referenced', NEW.times_referenced,
            'is_active', NEW.is_active
        )
    )
    ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title,
        content = EXCLUDED.content,
        confidence = EXCLUDED.confidence,
        tier = EXCLUDED.tier,
        meta = EXCLUDED.meta,
        last_used_at = CURRENT_TIMESTAMP
    RETURNING id INTO mem_id;

    -- Link back to memory_block
    NEW.memory_block_id := mem_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply dual-write trigger to user_preferences
CREATE TRIGGER sync_preference_to_memory_trigger
    BEFORE INSERT OR UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION sync_preference_to_memory();

-- Function: Dual-write entity to memory_blocks
CREATE OR REPLACE FUNCTION sync_entity_to_memory()
RETURNS TRIGGER AS $$
DECLARE
    mem_id UUID;
BEGIN
    -- Insert or update memory_block
    INSERT INTO memory_blocks (
        title,
        content,
        type,
        tier,
        confidence,
        tags,
        source,
        lineage,
        meta
    ) VALUES (
        NEW.entity_name,
        NEW.entity_data::TEXT,
        'entity',
        'long_term',  -- Entities default to long-term storage
        NEW.confidence,
        ARRAY[NEW.entity_type],
        ARRAY['entities_table'],
        ARRAY['entity:' || NEW.id::TEXT],
        jsonb_build_object(
            'entity_id', NEW.id,
            'entity_type', NEW.entity_type,
            'last_referenced', NEW.last_referenced,
            'reference_count', NEW.reference_count
        )
    )
    ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title,
        content = EXCLUDED.content,
        confidence = EXCLUDED.confidence,
        meta = EXCLUDED.meta,
        last_used_at = CURRENT_TIMESTAMP
    RETURNING id INTO mem_id;

    -- Link back to memory_block
    NEW.memory_block_id := mem_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply dual-write trigger to entities
CREATE TRIGGER sync_entity_to_memory_trigger
    BEFORE INSERT OR UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION sync_entity_to_memory();

-- View: Recent conversations with context (for analytics endpoints)
CREATE VIEW recent_conversations_with_context AS
SELECT
    c.id,
    c.session_id,
    c.user_input,
    c.assistant_response,
    c.intent,
    c.timestamp,
    c.response_time_ms,
    sa.primary_intent AS session_primary_intent,
    sa.avg_response_time_ms AS session_avg_response_time
FROM conversations c
LEFT JOIN session_analytics sa ON c.session_id = sa.session_id
WHERE c.timestamp >= CURRENT_TIMESTAMP - INTERVAL '7 days'
ORDER BY c.timestamp DESC;

-- View: Active preferences (for /memory/preferences endpoint)
CREATE VIEW active_preferences AS
SELECT
    preference_key,
    preference_value,
    preference_type,
    confidence_score,
    source,
    updated_at,
    memory_block_id
FROM user_preferences
WHERE is_active = TRUE
ORDER BY updated_at DESC;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hassistant;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hassistant;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO hassistant;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Legacy schema initialized successfully';
    RAISE NOTICE 'Tables created: conversations, messages, user_preferences, entities, session_analytics';
    RAISE NOTICE 'Dual-write triggers enabled for user_preferences and entities';
    RAISE NOTICE 'Views created: recent_conversations_with_context, active_preferences';
END $$;
