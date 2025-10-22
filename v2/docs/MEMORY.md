# Memory Integration (Step 2.5)

Complete documentation for the Memory ↔ LLM Integration system.

## Table of Contents

- [Architecture](#architecture)
- [Flow Diagram](#flow-diagram)
- [Components](#components)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Heuristics](#heuristics)
- [Metrics](#metrics)
- [Home Assistant Integration](#home-assistant-integration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Architecture

The memory integration adds a **pre-retrieval → context injection → LLM → post-storage** loop to the orchestrator, enabling conversations to reference past context.

### Key Features

- **Turn Traceability**: Every request gets a UUID (`turn_id`) that flows through the entire pipeline
- **Hash-based Deduplication**: Normalized text creates stable hashes to prevent near-duplicates
- **Ephemeral vs Durable**: Short replies are marked `chat_ephemeral`, longer ones `chat_assistant`
- **Kind Filtering**: Search can prefer certain memory types (notes > tasks > chat)
- **LRU Cache**: Recent queries cached (60s TTL) to reduce latency
- **PII Redaction**: Emails, phones, SSN, credit cards → placeholders
- **Live Configuration**: Min score and top-k tunable from Home Assistant UI

---

## Flow Diagram

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │ turn_id = uuid()
         ▼
┌─────────────────────────────────────┐
│     Orchestrator (main.py)          │
│  ┌──────────────────────────────┐   │
│  │ 1. Pre-Retrieval             │   │
│  │    - mem.search(q, turn_id)  │   │
│  │    - Filter by score ≥0.62   │   │
│  │    - Filter by kind          │   │
│  │    - Truncate to 1200 chars  │   │
│  └──────────┬───────────────────┘   │
│             ▼                        │
│  ┌──────────────────────────────┐   │
│  │ 2. Context Injection         │   │
│  │    ### Retrieved memory...   │   │
│  │    {ctx}                     │   │
│  │    ---                       │   │
│  │    User: {query}             │   │
│  └──────────┬───────────────────┘   │
│             ▼                        │
│  ┌──────────────────────────────┐   │
│  │ 3. LLM Call                  │   │
│  │    ollama.generate(prompt)   │   │
│  └──────────┬───────────────────┘   │
│             ▼                        │
│  ┌──────────────────────────────┐   │
│  │ 4. Post-Storage              │   │
│  │    - Check worth_saving()    │   │
│  │    - Compute hash for dedup  │   │
│  │    - Redact PII              │   │
│  │    - Ephemeral vs. durable   │   │
│  │    - mem.add(both sides)     │   │
│  └──────────┬───────────────────┘   │
│             ▼                        │
│  ┌──────────────────────────────┐   │
│  │ 5. Metrics & Return          │   │
│  │    {turn_id, hits, ctx_chars}│   │
│  └──────────────────────────────┘   │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│     Letta Bridge (server.py)        │
│  - /memory/search (with filters)    │
│  - /memory/add (with dedup)         │
│  - /config (autosave, min_score)    │
│  - /stats (hits, used, queries)     │
│  - /turns/{id} (debug)              │
│  - /metrics (Prometheus)            │
└─────────────────────────────────────┘
```

---

## Components

### 1. Database Schema

**File**: `v2/scripts/05_memory_dedup.sql`

Adds:
- `hash_id` column for deduplication (16-char hex, unique)
- `updated_at` timestamp with automatic trigger
- Indexes: `kind_created`, `hash`, `meta_role`, `meta_turn_id`

**Apply**:
- The v2 `docker-compose.yml` now ships a `memory-migrations` one-shot service that runs this script on every boot.
- For an already running stack, trigger it manually:
  ```bash
  docker compose -f v2/docker-compose.yml run --rm memory-migrations
  ```

### 2. Background Task Manager

**File**: `v2/services/glados-orchestrator/background.py`

Safe fire-and-forget task spawning with:
- Automatic cleanup on task completion
- Error logging (throttled)
- Graceful shutdown handling

### 3. Memory Client

**File**: `v2/services/glados-orchestrator/memory_client.py`

Features:
- LRU cache (configurable size, 60s TTL)
- Timeouts: connect=2s, read=6s
- Single retry with exponential backoff (200-400ms)
- Fire-and-forget adds (don't block on failures)
- Cache invalidation on config changes
- Throttled error logging (1/minute)

### 4. Memory Policy

**File**: `v2/services/glados-orchestrator/memory_policy.py`

Heuristics for:
- **Worth Saving**: Length, boring patterns, structure
- **PII Redaction**: emails, phones, SSN, credit cards
- **Hash Computation**: Normalized sha256 for dedup
- **Kind Classification**: Ephemeral vs durable based on length

### 5. Letta Bridge Enhancements

**File**: `v2/services/letta-bridge/server.py`

New endpoints:
- `POST /memory/add` - Dedup-aware upsert (returns `deduped: true/false`)
- `POST /memory/search` - Kind filtering via SQL
- `POST /stats/hit` - Signal memory usage to update metrics
- `GET /turns/{turn_id}` - Debug endpoint (gated by `DEBUG_TURNS=1`)
- `GET/POST /config` - Live config (autosave, min_score, top_k)

Metrics:
- `memory_search_total` - All searches
- `memory_search_used_total` - Searches where memory was relevant
- `memory_additions_total{role,kind}` - Memories added by type
- `memory_dedup_hits_total` - Dedup upserts
- `search_latency_ms` - Search histogram
- `add_latency_ms` - Add histogram

### 6. GLaDOS Orchestrator

**File**: `v2/services/glados-orchestrator/main.py`

Memory-aware chat service:
- `POST /chat` - Chat endpoint with memory hooks
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

Metrics:
- `orchestrator_memory_pre_ms` - Pre-retrieval latency
- `orchestrator_memory_post_ms` - Post-storage latency
- `orchestrator_ctx_chars` - Context characters injected

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_URL` | `http://letta-bridge:8010` | Letta-bridge endpoint |
| `MEMORY_AUTOSAVE_ON` | `1` | Enable automatic memory storage |
| `MEMORY_TOP_K` | `6` | Max memories to retrieve |
| `MEMORY_MIN_SCORE` | `0.62` | Minimum relevance score |
| `MEMORY_MAX_CTX_CHARS` | `1200` | Max context chars injected |
| `MEMORY_DURABLE_THRESHOLD` | `80` | Chars to promote ephemeral→durable |
| `MEMORY_CACHE_SIZE` | `50` | LRU cache entries |
| `MEMORY_CONNECT_TIMEOUT` | `2.0` | HTTP connect timeout (s) |
| `MEMORY_READ_TIMEOUT` | `6.0` | HTTP read timeout (s) |
| `DEBUG_TURNS` | `0` | Enable /turns/{id} debug endpoint |

### Docker Compose

All environment variables are configured in `v2/docker-compose.yml` under the `orchestrator` service.

---

## API Reference

### POST /chat

**Endpoint**: `http://orchestrator:8020/chat`

**Request**:
```json
{
  "input": "Where is the HDMI dongle?",
  "system_prompt": "You are GLaDOS..." (optional)
}
```

**Response**:
```json
{
  "turn_id": "550e8400-e29b-41d4-a716-446655440000",
  "reply": "Based on my memory, the HDMI dongle is in the left desk drawer.",
  "memory_hits": 3,
  "ctx_chars": 142
}
```

### POST /memory/search

**Endpoint**: `http://letta-bridge:8010/memory/search`

**Request**:
```json
{
  "q": "Where is the HDMI dongle?",
  "top_k": 6,
  "turn_id": "550e8400...",
  "filter": {
    "kinds": ["note", "task", "doc"]
  }
}
```

**Response**:
```json
{
  "results": [
    {
      "id": "123",
      "text": "The spare HDMI dongle is in the left desk drawer",
      "kind": "note",
      "meta": {"ts": 1710123456},
      "score": 0.87,
      "created_at": "2025-10-15T12:00:00Z"
    }
  ],
  "turn_id": "550e8400..."
}
```

### POST /memory/add

**Endpoint**: `http://letta-bridge:8010/memory/add`

**Request**:
```json
{
  "text": "The HDMI dongle is in the drawer",
  "kind": "chat_user",
  "source": "orchestrator",
  "hash_id": "a3f5d8e2c1b4" (optional),
  "meta": {
    "turn_id": "550e8400...",
    "role": "user",
    "ctx_hits": 3,
    "ts": 1710123456
  }
}
```

**Response**:
```json
{
  "id": "550e8400-...",
  "hash_id": "a3f5d8e2c1b4",
  "deduped": false
}
```

### GET/POST /config

**Endpoint**: `http://letta-bridge:8010/config`

**GET Response**:
```json
{
  "autosave": true,
  "min_score": 0.62,
  "top_k": 6,
  "ingest": true
}
```

**POST Request**:
```json
{
  "autosave": false,
  "min_score": 0.70
}
```

### GET /stats

**Endpoint**: `http://letta-bridge:8010/stats`

**Response**:
```json
{
  "total": 142,
  "embedded": 140,
  "pending": 2,
  "last_memory_hits": 3,
  "last_used": true,
  "last_queries": [
    {"query": "HDMI dongle?", "results": 3, "ts": 1710123456}
  ]
}
```

### GET /turns/{turn_id}

**Endpoint**: `http://letta-bridge:8010/turns/{turn_id}`

**Requires**: `DEBUG_TURNS=1` environment variable

**Response**:
```json
{
  "turn_id": "550e8400-...",
  "count": 2,
  "memories": [
    {
      "id": "123",
      "text": "Where is the HDMI dongle?",
      "kind": "chat_user",
      "meta": {"turn_id": "550e8400...", "role": "user"},
      "created_at": "2025-10-15T12:00:00Z",
      "has_embedding": true
    },
    {
      "id": "124",
      "text": "The HDMI dongle is in the left desk drawer.",
      "kind": "chat_assistant",
      "meta": {"turn_id": "550e8400...", "role": "assistant", "ctx_hits": 3},
      "created_at": "2025-10-15T12:00:05Z",
      "has_embedding": true
    }
  ]
}
```

---

## Heuristics

### Worth Saving

Logic in `memory_policy.py`:

**User queries**: Always saved (unless autosave is off)

**Assistant replies**:
- `< 80 chars` → `chat_ephemeral` (can be pruned later)
- `≥ 80 chars` → `chat_assistant` (durable)
- Contains "remember that", "save this", "don't forget" → force durable

**Filtered out**:
- Too short (< 12 chars)
- Boring patterns: "ok", "thanks", "hmm", etc.

### Deduplication

- Compute `sha256(normalize(text))[:16]` as hash_id
- Normalized: lowercase, stripped whitespace
- Upsert on `hash_id` prevents near-duplicates

### PII Redaction

Applied on storage (belt & suspenders):
- Emails → `[email]`
- Phone numbers → `[phone]`
- SSN → `[ssn]`
- Credit cards → `[card]`

---

## Metrics

### Orchestrator Metrics

Available at `http://orchestrator:8020/metrics`:

- `orchestrator_memory_pre_ms` - Pre-retrieval latency (histogram)
  - Buckets: 10, 25, 50, 100, 200, 500, 1000, 2000, 5000ms
- `orchestrator_memory_post_ms` - Post-storage latency (histogram)
- `orchestrator_ctx_chars` - Context characters injected (histogram)

### Letta-Bridge Metrics

Available at `http://letta-bridge:8010/metrics`:

- `memory_search_total` - Total searches (counter)
- `memory_search_used_total` - Searches where memory was used (counter)
- `memory_additions_total{role,kind}` - Memories added (counter with labels)
- `memory_dedup_hits_total` - Dedup upserts (counter)
- `letta_search_latency_ms` - Search latency (histogram)
- `letta_add_latency_ms` - Add latency (histogram)

---

## Home Assistant Integration

### Entities

**File**: `v2/ha_config/packages/memory.yaml`

**Controls**:
- `switch.memory_autosave` - Enable/disable automatic storage
- `input_number.memory_min_score` - Adjust recall threshold (0.0-1.0)

**Sensors**:
- `sensor.memory_total` - Total memories (60s poll)
- `sensor.memory_recall_hits` - Last query's hit count (15s poll)
- `sensor.memory_last_used` - Whether memory was used in last query (15s poll)
- `sensor.memory_context_chars` - Context chars injected (30s poll)
- `sensor.memory_recall_rate` - % of searches where memory was used (30s poll)

**Automations**:
- `memory_score_tuning` - Syncs `input_number.memory_min_score` to letta-bridge config

### Dashboard Example

```yaml
type: entities
title: Memory System
entities:
  - sensor.memory_total
  - sensor.memory_recall_hits
  - sensor.memory_recall_rate
  - sensor.memory_context_chars
  - switch.memory_autosave
  - input_number.memory_min_score
```

---

## Testing

### Unit Tests

**File**: `v2/tests/test_memory_integration.py`

Run with:
```bash
pytest v2/tests/test_memory_integration.py -v
```

Tests:
- Basic retrieval flow
- Kind filtering
- Autosave toggle
- Deduplication
- Stats endpoint
- Config persistence
- End-to-end chat integration

### Smoke Test

**File**: `v2/tests/AT_chat_memory_smoke.sh`

Run with:
```bash
bash v2/tests/AT_chat_memory_smoke.sh
```

Tests:
- Seed fact → ask question → verify recall
- Metrics update properly
- Autosave toggle works

---

## Troubleshooting

### Memory not recalling

1. **Check sensor values**:
   - `sensor.memory_recall_hits` - Is it > 0?
   - `sensor.memory_recall_rate` - Is it > 0%?

2. **Lower score threshold**:
   - Try setting `input_number.memory_min_score` to 0.50

3. **Check logs**:
   ```bash
   docker logs hassistant_v2_orchestrator | grep "Memory search"
   docker logs hassistant_v2_lettabridge | grep "search"
   ```

4. **Verify embeddings**:
   ```bash
   curl http://localhost:8010/stats
   # Check that embedded ≈ total (pending should be low)
   ```

### Latency spikes

1. **Check metrics**:
   ```bash
   curl http://localhost:8020/metrics | grep orchestrator_memory_pre_ms
   ```

2. **If p99 > 200ms**:
   - Check memembed CPU/GPU usage
   - Increase `MEMORY_CACHE_SIZE` to 100+
   - Lower `MEMORY_TOP_K` to 3-4

3. **Check for timeouts**:
   ```bash
   docker logs hassistant_v2_orchestrator | grep "timeout"
   ```

### Too many memories stored

1. **Increase durable threshold**:
   - Set `MEMORY_DURABLE_THRESHOLD=100` (only long replies are durable)

2. **Check addition rate**:
   ```bash
   curl http://localhost:8010/metrics | grep memory_additions_total
   ```

3. **Enable ephemeral pruning** (future feature - night job)

### PII leakage

1. **Review redaction patterns** in `memory_policy.py`
2. **Add custom patterns** for your domain
3. **Audit memories**:
   ```bash
   curl http://localhost:8010/memory/search \
     -H "Content-Type: application/json" \
     -d '{"q":"test"}'
   ```

### Deduplication not working

1. **Check hash_id field exists**:
   ```bash
   docker exec hassistant_v2_postgres psql -U glados -d glados \
     -c "SELECT hash_id FROM memories LIMIT 5;"
   ```

2. **Check for dedup hits**:
   ```bash
   curl http://localhost:8010/metrics | grep memory_dedup_hits_total
   ```

3. **Verify migration was applied**:
   ```bash
   docker exec hassistant_v2_postgres psql -U glados -d glados \
     -c "\d memories"
   # Should show hash_id column with unique constraint
   ```

---

## Quick Commands

```bash
# Apply SQL migration
docker exec -i hassistant_v2_postgres psql -U glados -d glados < v2/scripts/05_memory_dedup.sql

# Build and start services
docker compose -f v2/docker-compose.yml up -d --build orchestrator letta-bridge

# Run tests
pytest v2/tests/test_memory_integration.py -v
bash v2/tests/AT_chat_memory_smoke.sh

# Check health
curl http://localhost:8020/health
curl http://localhost:8010/health

# View metrics
curl http://localhost:8020/metrics | grep orchestrator_memory
curl http://localhost:8010/metrics | grep memory_

# Manual test
curl -X POST http://localhost:8020/chat \
  -H "Content-Type: application/json" \
  -d '{"input":"Where is the HDMI dongle?"}'

# Debug a turn (requires DEBUG_TURNS=1)
export DEBUG_TURNS=1
docker restart hassistant_v2_lettabridge
curl http://localhost:8010/turns/550e8400-e29b-41d4-a716-446655440000
```

---

## Next Steps

After Step 2.5, consider:

1. **Replace fake embeddings**: Integrate sentence-transformers or OpenAI embeddings in mem-embed
2. **Night job**: Implement ephemeral memory pruning and daily summaries
3. **Promote button**: Add HA service to force-persist last reply
4. **Context ranking**: Sort retrieved memories by kind priority + score
5. **Vision integration** (Step 3): Add multimodal context from vision gateway

---

**Documentation Version**: Step 2.5
**Last Updated**: 2025-10-15
