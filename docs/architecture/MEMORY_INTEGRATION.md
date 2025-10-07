# Memory Integration - Letta-Style Architecture

HAssistant implements a sophisticated memory system inspired by Letta (formerly MemGPT) for persistent, context-aware AI interactions. This document describes the architecture, usage, and maintenance of the memory integration.

## Architecture Overview

```
┌─────────────────┐
│  Qwen Agent /   │  Memory operations via REST API
│  Home Assistant │
└────────┬────────┘
         │
    ┌────▼─────┐
    │  Letta   │  FastAPI Bridge (Port 8081)
    │  Bridge  │  - Memory CRUD operations
    │          │  - Semantic search
    └────┬─────┘  - Daily briefing
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│ Redis │ │Postgres│  Cache + Persistent storage
│ Cache │ │pgvector│  Vector embeddings
└───────┘ └────────┘
```

## Components

### 1. Letta Bridge API (`letta_bridge/`)

FastAPI service providing REST endpoints for memory operations:

- **POST /memory/add** - Create new memory entries
- **GET /memory/search** - Semantic search across memories
- **POST /memory/pin** - Pin important memories
- **POST /memory/forget** - Demote or remove memories
- **GET /daily_brief** - Get recent insights and important memories
- **GET /healthz** - Health check endpoint
- **GET /metrics** - Service metrics (stub)

### 2. PostgreSQL with pgvector

Persistent storage with vector similarity search:

- **memory_blocks** - Core memory storage with tiered retention
- **memory_embeddings** - Vector embeddings for semantic search (1536-dim)
- **agent_state** - Letta agent state persistence
- **conversations**, **messages** - Legacy compatibility tables
- **user_preferences**, **entities** - Structured knowledge storage

### 3. Redis Cache

Ephemeral session data and rate limiting:

- Memory operation cooldowns
- Session state caching
- Quick-access temporary data

## Memory Tiers

The system implements a tiered memory architecture:

| Tier | Retention | Use Case |
|------|-----------|----------|
| **session** | 1 hour | Current conversation context |
| **short_term** | 7 days | Recent interactions |
| **medium_term** | 30 days | Important recent facts |
| **long_term** | 1 year | Significant knowledge |
| **permanent** | Forever | Core facts, never evicted |

### Automatic Eviction

Unpinned memories are automatically evicted based on:
- Tier retention policy
- Last access time (`last_used_at`)
- Pin status (pinned memories are never evicted)

## Memory Types

```python
# Available memory types
MemType = Literal[
    "fact",         # Verified factual information
    "event",        # Time-bound occurrences
    "task",         # Action items or todos
    "preference",   # User preferences
    "insight",      # Derived knowledge
    "entity",       # Named entities (people, places, things)
    "note",         # Unstructured notes
    "conversation", # Dialog excerpts
    "knowledge"     # Structured knowledge
]
```

## API Usage Examples

### Adding a Memory

```bash
curl -X POST http://localhost:8081/memory/add \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "type": "fact",
    "title": "User prefers GLaDOS personality",
    "content": "The user explicitly requested sarcastic, witty responses inspired by GLaDOS from Portal.",
    "tags": ["preference", "personality"],
    "source": ["user_conversation"],
    "confidence": 0.95,
    "tier": "long",
    "pin": true,
    "generate_embedding": true
  }'
```

### Searching Memories

```bash
# Semantic search
curl "http://localhost:8081/memory/search?q=user%20personality%20preferences&k=5&tiers=long,permanent&types=fact,preference" \
  -H "x-api-key: your-api-key"

# Response includes cosine similarity scores for ranking
```

### Pinning a Memory

```bash
curl -X POST http://localhost:8081/memory/pin \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "pin": true
  }'
```

### Daily Brief

```bash
# Get important memories from last 24 hours
curl "http://localhost:8081/daily_brief" \
  -H "x-api-key: your-api-key"
```

## Database Schema

### memory_blocks

Core table for all memories:

```sql
CREATE TABLE memory_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,              -- Memory type (fact, event, etc.)
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',        -- Categorization
    source TEXT[] DEFAULT '{}',      -- Origin tracking
    lineage TEXT[] DEFAULT '{}',     -- Memory derivation chain
    confidence REAL DEFAULT 0.7,     -- Reliability score [0-1]
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    tier TEXT NOT NULL,              -- Retention tier
    pin BOOLEAN DEFAULT FALSE,       -- Protected from eviction
    meta JSONB DEFAULT '{}'          -- Flexible metadata
);
```

### memory_embeddings

Vector embeddings for semantic search:

```sql
CREATE TABLE memory_embeddings (
    memory_id UUID REFERENCES memory_blocks(id) ON DELETE CASCADE,
    embedding VECTOR(1536),          -- OpenAI ada-002 compatible
    PRIMARY KEY (memory_id)
);
```

### Indexes

Optimized for common query patterns:

- **GIN indexes**: tags, source, meta (fast array/JSON search)
- **IVFFlat index**: vector embeddings (approximate nearest neighbor)
- **btree indexes**: tier, type, timestamps (filtering/sorting)
- **Full-text search**: title and content (keyword search)

## Environment Configuration

Required environment variables (see `.env.example`):

```bash
# PostgreSQL
POSTGRES_PASSWORD=secure_random_password
LETTA_PG_URI=postgresql://hassistant:password@hassistant-postgres:5432/hassistant

# Redis
REDIS_PASSWORD=secure_random_password
LETTA_REDIS_URL=redis://:password@hassistant-redis:6379/0

# Letta Bridge
BRIDGE_API_KEY=secure_random_api_key
EMBED_DIM=1536
DAILY_BRIEF_WINDOW_HOURS=24

# Shared automation clients
VISION_GATEWAY_URL=http://vision-gateway:8088
WINDOWS_VOICE_CONTROL_URL=http://windows-voice-control:8085
```

## Deployment

### Docker Compose

Services are defined in `docker-compose.yml`:

```bash
# Start all services including memory stack
docker compose up -d

# Check service health
docker compose ps
docker compose logs letta-bridge
docker compose logs postgres
docker compose logs redis

# Verify database initialization
docker compose logs postgres | grep "Letta memory schema initialized"
```

### Database Initialization

SQL scripts in `scripts/` run automatically on first startup:

1. **01_enable_pgvector.sql** - Enable pgvector extension
2. **02_letta_schema.sql** - Core Letta memory tables and functions
3. **03_legacy_schema.sql** - Backward compatibility tables
4. **04_indexes.sql** - Performance optimization indexes

### Health Checks

```bash
# Letta Bridge health
curl -H "x-api-key: your-key" http://localhost:8081/healthz

# PostgreSQL connectivity
docker exec hassistant-postgres pg_isready -U hassistant

# Redis connectivity
docker exec hassistant-redis redis-cli --raw incr ping
```

## Maintenance

### Memory Eviction

Automatic cleanup via SQL function:

```sql
-- Run manually or via scheduled job
SELECT * FROM evict_old_memories();

-- Returns eviction counts by tier
```

### Memory Promotion

Promote important short-term memories to long-term:

```sql
SELECT promote_memory_tier(
    'memory-uuid-here'::UUID,
    'long_term'
);
```

### Database Backups

```bash
# Backup PostgreSQL
docker exec hassistant-postgres pg_dump -U hassistant hassistant > backup.sql

# Restore
docker exec -i hassistant-postgres psql -U hassistant hassistant < backup.sql

# Backup Redis
docker exec hassistant-redis redis-cli SAVE
docker cp hassistant-redis:/data/dump.rdb ./redis-backup.rdb
```

### Performance Monitoring

```bash
# Check index usage
docker exec hassistant-postgres psql -U hassistant -d hassistant -c "
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
"

# Check table sizes
docker exec hassistant-postgres psql -U hassistant -d hassistant -c "
SELECT relname AS table_name,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
"
```

## Integration with Home Assistant

The Qwen Agent can leverage memory for:

1. **Context Persistence** - Remember user preferences across sessions
2. **Personalization** - Adapt responses based on learned preferences
3. **Task Management** - Store and retrieve task memories
4. **Knowledge Base** - Build a persistent knowledge graph
5. **Conversation History** - Reference past interactions

### Example Integration (Qwen Agent)

```python
import httpx

async def store_preference(title: str, content: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://hassistant-letta-bridge:8081/memory/add",
            headers={"x-api-key": os.getenv("BRIDGE_API_KEY")},
            json={
                "type": "preference",
                "title": title,
                "content": content,
                "tier": "long",
                "pin": True,
                "tags": ["user_preference"],
                "confidence": 0.9
            }
        )
        return response.json()

async def recall_relevant_memories(query: str, k: int = 5):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://hassistant-letta-bridge:8081/memory/search",
            headers={"x-api-key": os.getenv("BRIDGE_API_KEY")},
            params={
                "q": query,
                "k": k,
                "tiers": "medium,long,permanent"
            }
        )
        return response.json()
```

## Troubleshooting

### Letta Bridge not starting

```bash
# Check logs
docker compose logs letta-bridge

# Common issues:
# - PostgreSQL not ready (wait for health check)
# - Redis connection refused (check password)
# - Port 8081 already in use
```

### Vector search not working

```bash
# Verify pgvector extension
docker exec hassistant-postgres psql -U hassistant -d hassistant -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# Check embedding indexes
docker exec hassistant-postgres psql -U hassistant -d hassistant -c "\\d memory_embeddings"
```

### Slow search performance

```bash
# Reindex if data size changed significantly
docker exec hassistant-postgres psql -U hassistant -d hassistant -c "
REINDEX INDEX CONCURRENTLY idx_memory_embeddings_vector;
ANALYZE memory_embeddings;
"

# Adjust IVFFlat lists parameter (sqrt of row count)
# in scripts/04_indexes.sql and recreate index
```

## Future Enhancements

- [ ] Real embedding model (sentence-transformers, Ollama embeddings)
- [ ] Automatic memory consolidation (merge similar memories)
- [ ] Memory importance scoring (decay over time)
- [ ] Graph-based memory relationships
- [ ] Export/import memory snapshots
- [ ] Web UI for memory management
- [ ] A/B testing of embedding models
- [ ] Memory usage analytics dashboard

## References

- [Letta (MemGPT) Documentation](https://github.com/cpacker/MemGPT)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AsyncPG Documentation](https://magicstack.github.io/asyncpg/)

## License

MIT License - See LICENSE file for details
>>>>>>> origin/copilot/fix-e9e049ad-c6a5-4a70-a747-ea989eb1320b
