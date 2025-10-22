# Migration Guide: Orchestrator Refactor

## Overview

The GLaDOS Orchestrator has been refactored from an Ollama API proxy to a **Tool Provider**. This guide helps you migrate from the old architecture to the new one.

## What Changed?

### Architecture

**Before (v1.x):**
```
Home Assistant → Orchestrator (mimics Ollama) → Ollama
```

**After (v2.x):**
```
Home Assistant → Ollama (direct) → Orchestrator (tools)
```

### Key Differences

| Aspect | Old (v1.x) | New (v2.x) |
|--------|-----------|-----------|
| HA Connection | Points to Orchestrator | Points to Ollama directly |
| Model Management | Broken (couldn't list/pull) | Fully functional |
| Query Routing | Orchestrator decides Hermes vs Qwen | LLM decides via tools |
| Memory Access | Automatic on complex queries | Via tool calling |
| API Endpoints | `/api/chat`, `/api/tags` | `/tool/*` |
| Code Size | ~550 lines | ~300 lines |

## Migration Steps

### Step 1: Update Home Assistant Ollama Integration

1. Navigate to **Settings → Devices & Services**
2. Find your Ollama integration
3. Click **Configure** or **Reconfigure**
4. Change the URL:
   - **Old**: `http://hassistant-glados-orchestrator:8082`
   - **New**: `http://ollama-chat:11434`
5. Save the configuration

### Step 2: Verify Model Access

After updating the URL, you should now see:
- All available models in Home Assistant
- Ability to pull new models from the UI
- Model management working correctly

Test by:
1. Go to the Ollama integration
2. Click on the integration to see model list
3. Verify you see models like `hermes3`, `qwen3:4b-instruct-2507-q4_K_M`

### Step 3: Update Docker Services (if needed)

If you were pointing directly to the orchestrator, update your docker-compose.yml:

```yaml
# Old configuration - REMOVE if present
# glados-orchestrator:
#   ports:
#     - "11434:8082"  # Don't expose on Ollama's port

# New configuration - orchestrator on its own port
glados-orchestrator:
  ports:
    - "8082:8082"  # Keep orchestrator on 8082
```

Restart services:
```bash
docker compose down
docker compose up -d
```

### Step 4: Test Basic Functionality

Test that everything works:

```bash
# Test Ollama directly
curl http://ollama-chat:11434/api/tags

# Test Orchestrator tools
curl http://hassistant-glados-orchestrator:8082/tool/list

# Test get_time tool
curl http://hassistant-glados-orchestrator:8082/tool/get_time
```

### Step 5: Update Custom Automations (Optional)

If you have custom automations that call the orchestrator, they need updating.

**Old way (no longer works):**
```yaml
service: rest_command.call_orchestrator
data:
  message: "What time is it?"
```

**New way (use Ollama directly with tools):**
```yaml
service: conversation.process
data:
  text: "What time is it?"
  agent_id: conversation.ollama
```

For advanced tool integration, see [HA_OLLAMA_DIRECT_CONNECTION.md](HA_OLLAMA_DIRECT_CONNECTION.md).

## Behavioral Changes

### Query Processing

**Old Behavior:**
- Orchestrator automatically decided Hermes (fast) vs Qwen (complex)
- Memory lookup was automatic for complex queries
- No user control over routing

**New Behavior:**
- LLM decides when to use tools
- Memory lookup only when LLM determines it's needed
- More efficient - only calls tools when necessary
- Better for simple queries (no overhead)

### Memory Integration

**Old Behavior:**
```
User: "Turn on the lights"
→ Orchestrator detects as simple
→ Calls Hermes directly
→ No memory lookup
```

**New Behavior:**
```
User: "Turn on the lights"
→ HA sends to Ollama
→ LLM responds directly
→ No tool calls needed (faster!)
```

**Old Behavior (Complex):**
```
User: "What's my schedule?"
→ Orchestrator detects as complex
→ Calls Letta for memories
→ Calls Qwen for reasoning
→ Calls Hermes for personality
```

**New Behavior (Complex):**
```
User: "What did I say about my schedule?"
→ HA sends to Ollama
→ LLM decides to call letta_query tool
→ Orchestrator returns memories
→ LLM formats response
```

## Troubleshooting Migration

### Issue: Can't see models in Home Assistant

**Symptoms:** Model list is empty or shows only "glados"

**Solution:**
1. Verify HA Ollama URL points to `http://ollama-chat:11434`
2. Check Ollama is running: `docker ps | grep ollama-chat`
3. Test direct access: `curl http://ollama-chat:11434/api/tags`
4. Restart HA: Settings → System → Restart

### Issue: Conversations not working

**Symptoms:** "Failed to process" or timeout errors

**Solution:**
1. Check Ollama logs: `docker logs ollama-chat`
2. Verify model is loaded: `docker exec ollama-chat ollama list`
3. Test direct chat:
   ```bash
   curl http://ollama-chat:11434/api/chat -d '{
     "model": "hermes3",
     "messages": [{"role": "user", "content": "Hello"}],
     "stream": false
   }'
   ```

### Issue: Memory not working

**Symptoms:** LLM doesn't remember previous conversations

**Expected:** Memory is now opt-in via tool calling. The LLM will call `letta_query` when it determines context is needed.

**To force memory usage:**
- Ask explicitly: "What do you remember about X?"
- Reference past conversations: "Like we discussed before..."

### Issue: Responses slower than before

**Expected:** Direct Ollama connection should be faster for simple queries.

**If slower:**
1. Check if you're using a larger model
2. Verify GPU allocation: `docker exec ollama-chat nvidia-smi`
3. Check for unnecessary tool calls in logs

### Issue: Orchestrator shows errors

**Symptoms:** Orchestrator logs show "Ollama error" or similar

**Resolution:** 
- This is expected! Orchestrator no longer calls Ollama directly
- Orchestrator should only show tool-related logs
- Check with: `docker logs hassistant-glados-orchestrator`

## Rollback Procedure

If you need to rollback to the old architecture:

```bash
# Checkout the old version
git checkout <previous-commit>

# Rebuild and restart
docker compose build glados-orchestrator
docker compose restart glados-orchestrator

# Update HA Ollama URL back to orchestrator
# Settings → Devices & Services → Ollama → Configure
# URL: http://hassistant-glados-orchestrator:8082
```

## Feature Comparison

| Feature | Old | New | Notes |
|---------|-----|-----|-------|
| Basic conversations | ✅ | ✅ | Faster in new version |
| Model management | ❌ | ✅ | Now works properly |
| Memory integration | ✅ (auto) | ✅ (on-demand) | More efficient |
| Query routing | ✅ | ✅ | Now LLM-controlled |
| Time queries | ✅ (built-in) | ✅ (via tool) | Explicit tool call |
| Streaming | ✅ | ✅ | Same support |
| Custom tools | ❌ | ✅ | Easy to add |

## Testing Checklist

After migration, verify:

- [ ] Home Assistant can list Ollama models
- [ ] Can pull a new model from HA UI
- [ ] Basic query works: "Hello, how are you?"
- [ ] Time query works: "What time is it?"
- [ ] Memory query works: "What do you remember about X?"
- [ ] Orchestrator health check passes: `curl http://hassistant-glados-orchestrator:8082/healthz`
- [ ] Tool list returns: `curl http://hassistant-glados-orchestrator:8082/tool/list`
- [ ] No errors in logs: `docker logs hassistant-glados-orchestrator`

## Benefits of New Architecture

1. **Cleaner separation of concerns**: Ollama handles conversations, Orchestrator provides tools
2. **Simpler codebase**: ~50% less code, easier to maintain
3. **Better performance**: No unnecessary routing overhead
4. **More flexible**: Easy to add new tools
5. **Standard patterns**: Uses Ollama's native function calling
6. **Better debugging**: Clear separation makes issues easier to diagnose

## Getting Help

If you encounter issues:

1. Check logs:
   ```bash
   docker logs ollama-chat
   docker logs hassistant-glados-orchestrator
   docker logs hassistant-homeassistant
   ```

2. Verify services are running:
   ```bash
   docker ps | grep -E "(ollama|orchestrator|homeassistant)"
   ```

3. Test endpoints individually (see Step 4 above)

4. Review documentation:
   - [ORCHESTRATOR_TOOL_PROVIDER.md](../architecture/ORCHESTRATOR_TOOL_PROVIDER.md)
   - [HA_OLLAMA_DIRECT_CONNECTION.md](HA_OLLAMA_DIRECT_CONNECTION.md)

5. Open an issue on GitHub with:
   - Steps you followed
   - Error messages from logs
   - Output of test commands
   - Your docker-compose.yml (without secrets)
