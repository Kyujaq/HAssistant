# Step 2.5: Memory ↔ LLM Integration - Deployment Guide

## Implementation Summary

**Status**: ✅ All code complete - Ready for deployment

**What Was Built**:
- **Database Migration**: Hash-based deduplication with performance indexes
- **Memory Client**: Async HTTP client with LRU cache, timeouts, retries
- **Memory Policy**: Smart heuristics for storage decisions and PII redaction
- **Letta-Bridge Enhancements**: New endpoints for dedup, filtering, config, metrics
- **Orchestrator Service**: New FastAPI service implementing memory-aware chat
- **Home Assistant Integration**: Controls, sensors, and automations
- **Tests**: Unit tests + end-to-end smoke test
- **Documentation**: Comprehensive MEMORY.md guide

## Architecture Approach

**Modified Existing**:
- `v2/services/letta-bridge/server.py` - Enhanced with new endpoints while preserving structure
- `v2/docker-compose.yml` - Added orchestrator service and healthcheck

**Created New**:
- `v2/scripts/05_memory_dedup.sql` - Database migration
- `v2/services/glados-orchestrator/` - Complete new service (main.py, background.py, memory_client.py, memory_policy.py, Dockerfile, requirements.txt)
- `v2/ha_config/packages/memory.yaml` - HA integration package
- `v2/tests/test_memory_integration.py` - Unit tests
- `v2/tests/AT_chat_memory_smoke.sh` - Smoke test
- `v2/docs/MEMORY.md` - Documentation

## Deployment Steps

### 1. Apply Database Migration

```bash
# Verify postgres is running
docker ps | grep hassistant_v2_pg

# Apply schema updates
docker exec -i hassistant_v2_pg psql -U glados -d glados < v2/scripts/05_memory_dedup.sql

# Verify migration
docker exec -i hassistant_v2_pg psql -U glados -d glados -c "\d memories"
# Should show: hash_id text NOT NULL, updated_at timestamptz
```

### 2. Build and Start Services

```bash
cd /home/qjaq/HAssistant

# Build new orchestrator and updated letta-bridge
docker compose -f v2/docker-compose.yml build orchestrator letta-bridge

# Start services
docker compose -f v2/docker-compose.yml up -d orchestrator letta-bridge

# Check logs
docker compose -f v2/docker-compose.yml logs -f orchestrator
docker compose -f v2/docker-compose.yml logs -f letta-bridge
```

### 3. Verify Services

```bash
# Health checks
curl -fsS http://localhost:8010/health  # letta-bridge
curl -fsS http://localhost:8020/health  # orchestrator

# Check metrics
curl -fsS http://localhost:8010/metrics | grep memory_
curl -fsS http://localhost:8020/metrics | grep orchestrator_

# Test memory add
curl -X POST http://localhost:8010/memory/add \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test memory","kind":"note","source":"manual"}'

# Test memory search
curl -X POST http://localhost:8010/memory/search \
  -H 'Content-Type: application/json' \
  -d '{"q":"test"}'

# Test orchestrator chat
curl -X POST http://localhost:8020/chat \
  -H 'Content-Type: application/json' \
  -d '{"input":"Hello, what is 2+2?"}'
```

### 4. Run Tests

```bash
cd /home/qjaq/HAssistant

# Unit tests (requires services running)
pytest v2/tests/test_memory_integration.py -v

# Smoke test
bash v2/tests/AT_chat_memory_smoke.sh
```

Expected output:
```
🧪 Memory Integration Smoke Test
==================================
1️⃣  Seeding memory...
   ✓ Memory added: <uuid>
2️⃣  Baseline check (What is 2+2?)...
   Reply: 4
3️⃣  Testing memory recall...
   Turn ID: <uuid>
   Memory hits: 1
   Reply: ...left desk drawer...
4️⃣  Verifying recall...
   ✅ Recall worked - reply mentions drawer!
5️⃣  Checking metrics...
   ✅ Metrics look good
6️⃣  Testing autosave toggle...
   ✅ Autosave off works
==================================
🎉 All smoke tests passed!
```

### 5. Home Assistant Integration

```bash
# Copy HA package
docker cp v2/ha_config/packages/memory.yaml homeassistant:/config/packages/

# Or if you have direct access to ha_config folder:
cp v2/ha_config/packages/memory.yaml ../assistant/ha_config/packages/

# Restart Home Assistant
# Settings → System → Restart
```

**Verify in HA UI**:
1. Go to Developer Tools → States
2. Look for entities:
   - `sensor.memory_total`
   - `sensor.memory_recall_hits`
   - `sensor.memory_recall_rate`
   - `switch.memory_autosave`
   - `input_number.memory_min_score`

3. Create a dashboard card:
```yaml
type: entities
title: Memory System
entities:
  - sensor.memory_total
  - sensor.memory_recall_hits
  - sensor.memory_recall_rate
  - switch.memory_autosave
  - input_number.memory_min_score
```

### 6. Live Configuration

```bash
# Adjust recall threshold (0.0-1.0)
curl -X POST http://localhost:8010/config \
  -H 'Content-Type: application/json' \
  -d '{"min_score": 0.7, "top_k": 8}'

# Toggle autosave
curl -X POST http://localhost:8010/config \
  -H 'Content-Type: application/json' \
  -d '{"autosave": false}'

# Get current config
curl http://localhost:8010/config
```

## Testing the Full Flow

### Manual End-to-End Test

```bash
# 1. Seed a fact
curl -X POST http://localhost:8010/memory/add \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "The spare HDMI cable is in the blue toolbox on the top shelf",
    "kind": "note",
    "source": "manual"
  }'

# 2. Ask a question (should recall the fact)
curl -X POST http://localhost:8020/chat \
  -H 'Content-Type: application/json' \
  -d '{"input": "Where is the HDMI cable?"}' | jq .

# Should return:
# {
#   "turn_id": "<uuid>",
#   "reply": "The spare HDMI cable is in the blue toolbox on the top shelf",
#   "memory_hits": 1,
#   "ctx_chars": 67
# }

# 3. Check that the question and answer were auto-saved
curl -X POST http://localhost:8010/memory/search \
  -H 'Content-Type: application/json' \
  -d '{"q": "HDMI"}' | jq .

# Should show 3 memories:
# - Original note
# - User question (kind: chat_user)
# - Assistant reply (kind: chat_assistant or chat_ephemeral)
```

### Debug Turn Tracing

```bash
# Enable debug mode (if not already set)
docker compose -f v2/docker-compose.yml exec letta-bridge \
  sh -c 'export DEBUG_TURNS=1'

# Make a chat request and note the turn_id
TURN_ID=$(curl -X POST http://localhost:8020/chat \
  -H 'Content-Type: application/json' \
  -d '{"input": "Test message"}' | jq -r '.turn_id')

# Trace all memories for this turn
curl "http://localhost:8010/turns/${TURN_ID}" | jq .

# Should show all memories created during this turn with full metadata
```

## Monitoring

### Prometheus Metrics

**Letta-Bridge** (`http://localhost:8010/metrics`):
- `memory_additions_total{role,kind}` - Count of new memories by type
- `memory_dedup_hits_total` - Count of duplicate memory attempts
- `memory_search_total` - Total searches performed
- `memory_search_used_total` - Searches where memory was actually used
- `memory_search_duration_seconds` - Search latency histogram

**Orchestrator** (`http://localhost:8020/metrics`):
- `orchestrator_requests_total{endpoint}` - Request count by endpoint
- `orchestrator_memory_hits_histogram` - Distribution of memory hits per query
- `orchestrator_ctx_chars_sum` - Total context characters injected
- `orchestrator_ollama_duration_seconds` - LLM call latency

### Log Monitoring

```bash
# Follow orchestrator logs
docker compose -f v2/docker-compose.yml logs -f orchestrator

# Follow letta-bridge logs
docker compose -f v2/docker-compose.yml logs -f letta-bridge

# Search for errors
docker compose -f v2/docker-compose.yml logs orchestrator | grep ERROR
docker compose -f v2/docker-compose.yml logs letta-bridge | grep ERROR
```

## Troubleshooting

### Service Won't Start

```bash
# Check dependencies
docker compose -f v2/docker-compose.yml ps

# Ensure postgres, memory-embed, ollama-chat are healthy
# Rebuild if needed
docker compose -f v2/docker-compose.yml build orchestrator --no-cache
docker compose -f v2/docker-compose.yml up -d orchestrator
```

### No Memory Hits

**Check autosave**:
```bash
curl http://localhost:8010/config | jq .autosave
# Should return: true
```

**Check min_score threshold**:
```bash
curl http://localhost:8010/config | jq .min_score
# Try lowering: 0.62 → 0.5
curl -X POST http://localhost:8010/config \
  -H 'Content-Type: application/json' \
  -d '{"min_score": 0.5}'
```

**Check if embeddings are working**:
```bash
# Search should return results with scores
curl -X POST http://localhost:8010/memory/search \
  -H 'Content-Type: application/json' \
  -d '{"q": "test"}' | jq '.results[] | {text, score}'
```

### Deduplication Not Working

```bash
# Verify hash_id column exists
docker exec -i hassistant_v2_pg psql -U glados -d glados -c "\d memories"

# Try adding same memory twice
curl -X POST http://localhost:8010/memory/add \
  -H 'Content-Type: application/json' \
  -d '{"text":"Duplicate test","kind":"note","source":"test"}' | jq .deduped
# First: false
# Second: true
```

### HA Sensors Not Updating

```bash
# Check sensor URL is reachable from HA container
docker exec homeassistant curl -fsS http://letta-bridge:8010/stats

# Check HA logs
docker logs homeassistant 2>&1 | grep memory

# Force update
# Developer Tools → States → sensor.memory_total → "Update entity"
```

## Configuration Reference

### Environment Variables

**Orchestrator** (`docker-compose.yml`):
```yaml
- OLLAMA_URL=http://ollama-chat:11434
- OLLAMA_MODEL=qwen2.5:3b
- MEMORY_URL=http://letta-bridge:8010
- MEMORY_AUTOSAVE_ON=1           # 1=enabled, 0=disabled
- MEMORY_TOP_K=6                 # Number of memories to retrieve
- MEMORY_MIN_SCORE=0.62          # Similarity threshold (0.0-1.0)
- MEMORY_MAX_CTX_CHARS=1200      # Max context length to inject
- MEMORY_DURABLE_THRESHOLD=80    # Short reply threshold (chars)
- MEMORY_CACHE_SIZE=50           # LRU cache size
- MEMORY_CONNECT_TIMEOUT=2.0     # HTTP connect timeout (seconds)
- MEMORY_READ_TIMEOUT=6.0        # HTTP read timeout (seconds)
```

**Letta-Bridge**:
```yaml
- MEMORY_URL=http://memory-embed:8001
- DATABASE_URL=postgresql://glados:glados@postgres:5432/glados
- DEBUG_TURNS=0                  # Set to 1 to enable /turns/{id} endpoint
```

### Tuning Recommendations

**For better recall**:
- Increase `MEMORY_TOP_K` (6 → 10)
- Lower `MEMORY_MIN_SCORE` (0.62 → 0.5)
- Increase `MEMORY_MAX_CTX_CHARS` (1200 → 2000)

**For faster responses**:
- Decrease `MEMORY_TOP_K` (6 → 3)
- Increase `MEMORY_MIN_SCORE` (0.62 → 0.75)
- Decrease `MEMORY_MAX_CTX_CHARS` (1200 → 800)

**For less noise**:
- Increase `MEMORY_DURABLE_THRESHOLD` (80 → 120) - saves fewer ephemeral messages
- Set `MEMORY_AUTOSAVE_ON=0` - manual memory saving only

## Next Steps

### Immediate (Post-Deployment)

1. **Monitor metrics** - Watch for memory usage patterns, hit rates, latency
2. **Tune thresholds** - Adjust min_score and top_k based on actual performance
3. **Add sample data** - Seed common facts, preferences, reminders

### Short-Term Enhancements

1. **Replace fake embeddings** - Update `memory-embed` to use real model (sentence-transformers)
2. **Add memory tags** - Category/topic tags for better filtering
3. **Memory expiration** - Auto-evict old ephemeral memories
4. **HA voice integration** - Connect orchestrator to HA Assist pipeline

### Long-Term Ideas

1. **Multi-user support** - Per-user memory isolation
2. **Memory clustering** - Group related memories
3. **Proactive recall** - Trigger memory search on time/location context
4. **Memory dashboard** - Web UI for browsing/editing memories

## Success Criteria

✅ **All tests pass**: Unit tests + smoke test
✅ **Services healthy**: orchestrator and letta-bridge respond to health checks
✅ **Memory recall works**: Questions retrieve relevant seeded facts
✅ **Autosave works**: Conversations are automatically stored
✅ **Dedup works**: Same text doesn't create duplicate entries
✅ **HA sensors update**: Dashboard shows memory stats
✅ **Config tuning works**: Adjusting min_score affects recall
✅ **Metrics available**: Prometheus endpoints return data

## Support

- **Documentation**: See `v2/docs/MEMORY.md` for architecture details
- **API Reference**: See MEMORY.md § 7 for endpoint specs
- **Troubleshooting**: See MEMORY.md § 11 for common issues
- **Code**: All implementation in `v2/services/glados-orchestrator/` and `v2/services/letta-bridge/`
