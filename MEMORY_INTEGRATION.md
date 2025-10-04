# Memory Integration Guide

## Overview

HAssistant includes a sophisticated memory system powered by the Letta Bridge API. This system allows the assistant to store, retrieve, and manage contextual information about your home, conversations, and events.

## Architecture

The memory system consists of:
- **PostgreSQL with pgvector**: Vector database for semantic search
- **Redis**: Fast caching layer for recent operations
- **Letta Bridge API**: RESTful API for memory operations
- **Home Assistant Integration**: REST commands and sensors

## Memory Tiers

Memories are organized into tiers with different retention policies:

| Tier | Retention Period | Use Case |
|------|-----------------|----------|
| `session` | 1 hour | Temporary conversation context |
| `short` | 7 days | Recent events and interactions |
| `medium` | 30 days | Important patterns and preferences |
| `long` | 365 days | Significant events and knowledge |
| `permanent` | Forever | Critical information (never auto-evicted) |

## Memory Types

- `fact`: Objective information about your home or preferences
- `event`: Something that happened (state changes, activities)
- `task`: Things to do or remember
- `preference`: User likes/dislikes
- `insight`: Learned patterns or observations
- `entity`: Information about people, places, or things
- `conversation`: Dialog context
- `knowledge`: General information

## API Endpoints

### Add Memory
```bash
POST http://hassistant-letta-bridge:8081/memory/add
Headers: x-api-key: <your-api-key>

{
  "title": "Memory title",
  "content": "Detailed content",
  "type": "event",
  "tier": "short",
  "tags": ["automation", "sensor"],
  "source": ["ha://sensor.temperature"],
  "confidence": 0.85,
  "pin": false,
  "generate_embedding": true
}
```

### Search Memories
```bash
GET http://hassistant-letta-bridge:8081/memory/search?q=temperature&k=5&tiers=short,medium
Headers: x-api-key: <your-api-key>
```

### Pin/Unpin Memory
```bash
POST http://hassistant-letta-bridge:8081/memory/pin
Headers: x-api-key: <your-api-key>

{
  "id": "uuid-of-memory",
  "pin": true
}
```

### Forget Memory
```bash
POST http://hassistant-letta-bridge:8081/memory/forget
Headers: x-api-key: <your-api-key>

{
  "id": "uuid-of-memory",
  "reason": "outdated information"
}
```

### Daily Brief
```bash
GET http://hassistant-letta-bridge:8081/daily_brief
Headers: x-api-key: <your-api-key>
```

### Memory Maintenance
```bash
POST http://hassistant-letta-bridge:8081/memory/maintenance
Headers: x-api-key: <your-api-key>
```

## Home Assistant Integration

### REST Commands

The following REST commands are configured in `configuration.yaml`:

- `rest_command.letta_add_memory` - Add a new memory
- `rest_command.letta_memory_maintenance` - Run cleanup

### Sensors

- `sensor.letta_daily_brief` - Shows recent important memories

### Active Automations

1. **Daily Memory Maintenance** (`letta_memory_maintenance`)
   - Runs at 3:00 AM daily
   - Cleans up old memories based on tier retention policies
   
2. **Log Important State Changes** (`letta_log_important_events`)
   - Tracks presence changes (home/away)
   - Saves to medium-term memory
   - Automatically tagged and sourced

### Example Usage in Automations

```yaml
# Log a temperature alert
- service: rest_command.letta_add_memory
  data:
    title: "High Temperature Alert"
    content: "Living room temperature reached {{ states('sensor.living_room_temp') }}°C"
    tags: '["temperature", "alert", "living_room"]'
    source: '["ha://sensor.living_room_temp"]'
    tier: "medium"
    type: "event"
    confidence: 0.9
```

```yaml
# Log a conversation insight
- service: rest_command.letta_add_memory
  data:
    title: "User Preference: Lighting"
    content: "User prefers warm white lighting in the evening"
    tags: '["preference", "lighting", "evening"]'
    tier: "long"
    type: "preference"
    confidence: 0.85
    pin: true
```

## Configuration

### Environment Variables

Set in `.env` file or docker-compose.yml:

```bash
# API Key for Letta Bridge
BRIDGE_API_KEY=your-secure-api-key-here

# PostgreSQL connection
LETTA_PG_URI=postgresql://hassistant:password@hassistant-postgres:5432/hassistant

# Redis connection
LETTA_REDIS_URL=redis://:password@hassistant-redis:6379/0

# Embedding dimension (default: 1536 for OpenAI ada-002)
EMBED_DIM=1536

# Daily brief time window (hours)
DAILY_BRIEF_WINDOW_HOURS=24
```

### Security

1. **Change default API key**: Update `BRIDGE_API_KEY` in `.env`
2. **Update HA configuration**: Change the `x-api-key` in `ha_config/configuration.yaml`
3. **Change database passwords**: Update PostgreSQL and Redis passwords

## Maintenance

### Manual Cleanup

Run memory maintenance manually via Home Assistant:
```yaml
service: rest_command.letta_memory_maintenance
```

### Check Memory Usage

Query the database directly:
```sql
-- Count memories by tier
SELECT tier, COUNT(*) 
FROM memory_blocks 
GROUP BY tier;

-- Find old memories
SELECT tier, COUNT(*) 
FROM memory_blocks 
WHERE last_used_at < NOW() - INTERVAL '30 days'
GROUP BY tier;
```

### Backup Important Memories

Export memories before cleanup:
```sql
-- Export all pinned memories
COPY (
  SELECT * FROM memory_blocks WHERE pin = true
) TO '/tmp/pinned_memories.csv' CSV HEADER;
```

## Best Practices

1. **Use appropriate tiers**: Don't store temporary data in `permanent` tier
2. **Pin important memories**: Use `pin: true` for critical information
3. **Add meaningful tags**: Make memories searchable with relevant tags
4. **Include source**: Always track where information came from
5. **Set confidence**: Reflect uncertainty in your confidence scores
6. **Regular maintenance**: Let the daily cleanup run to prevent bloat

## Troubleshooting

### Memory not being added

1. Check API key is correct in both `.env` and `configuration.yaml`
2. Verify letta-bridge service is running: `docker ps | grep letta-bridge`
3. Check logs: `docker logs hassistant-letta-bridge`

### Search not finding memories

1. Ensure `generate_embedding: true` when adding memories
2. Check pgvector extension is installed in PostgreSQL
3. Verify embedding dimension matches (`EMBED_DIM`)

### Database growing too large

1. Run manual maintenance: `rest_command.letta_memory_maintenance`
2. Review pinned memories - unpin if no longer needed
3. Adjust tier retention policies in database schema if needed

## Future Enhancements

- Integration with LLM for automatic memory summarization
- Smart memory promotion (moving important short-term to long-term)
- Memory clustering and deduplication
- Advanced search with filters and scoring
- Memory visualization dashboard
