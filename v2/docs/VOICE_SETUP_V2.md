# Voice Assistant Setup - v2 (With Memory)

Quick guide to connect Home Assistant Assist to your memory-aware orchestrator.

## What You Get

Voice → Wyoming STT → **Orchestrator (with memory!)** → Wyoming TTS → Voice

✅ Full memory integration (remembers conversations)
✅ Intelligent routing (fast/deep paths, VL escalation)
✅ GPU-accelerated speech (CUDA Whisper + Piper)

---

## Prerequisites

Make sure these services are running:
```bash
docker ps | grep -E 'orchestrator|wyoming|ollama'
```

Expected:
- `hassistant_v2_orchestrator` (port 8020)
- `hassistant_v2_wyoming_proxy` (ports 10300, 10210)
- `hassistant_v2_ollama_text` (port 11435)

---

## Step 1: Add Wyoming Integrations in HA

### 1a. Add Wyoming STT (Speech-to-Text)

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Wyoming Protocol"**
3. Configure:
   - **Host**: `wyoming-openai` (or `hassistant_v2_wyoming_proxy` if using IP)
   - **Port**: `10300`
4. Save as **"Wyoming STT (Whisper STT)"**

### 1b. Add Wyoming TTS (Text-to-Speech)

1. **Settings → Devices & Services → Add Integration**
2. Search for **"Wyoming Protocol"**
3. Configure:
   - **Host**: `wyoming-openai`
   - **Port**: `10210`
4. Save as **"Wyoming TTS (Piper GLaDOS)"**

---

## Step 2: Add OpenAI Conversation (Points to Orchestrator)

1. **Settings → Devices & Services → Add Integration**
2. Search for **"OpenAI Conversation"**
3. Configure:
   - **API Key**: `sk-dummy` (any value, not validated)
   - **Base URL**: `http://orchestrator:8020/v1`
   - **Model**: `glados-orchestrator` (name doesn't matter, router auto-selects)
4. Save as **"GLaDOS Orchestrator"**

**Note**: The orchestrator's `/v1/chat/completions` endpoint is OpenAI-compatible, so HA's built-in integration works perfectly!

---

## Step 3: Create Assist Pipeline

1. **Settings → Voice Assistants → Add Assistant**
2. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `GLaDOS` |
| **Conversation Agent** | `GLaDOS Orchestrator` |
| **Speech-to-Text** | `Wyoming STT (Whisper STT)` |
| **Text-to-Speech** | `Wyoming TTS (Piper GLaDOS)` |
| **Wake Word** | _(Leave blank or use "Ok Nabu")_ |

3. Click **Create**

---

## Step 4: Test It!

### Test in HA UI

1. Go to **Settings → Voice Assistants**
2. Click **Assist** (microphone icon)
3. Say: **"What is 2+2?"**
4. You should hear GLaDOS respond!

### Test Memory Recall

1. Seed a memory:
```bash
curl -X POST http://localhost:8010/memory/add \
  -H 'Content-Type: application/json' \
  -d '{"text":"The user loves pizza and hates pineapple toppings","kind":"note","source":"manual"}'
```

2. Ask via voice: **"What do I like to eat?"**
3. GLaDOS should mention pizza!

### Test via API (for debugging)

```bash
# Direct orchestrator test
curl -X POST http://localhost:8020/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello, who are you?"}]
  }' | jq -r '.choices[0].message.content'
```

---

## Advanced Configuration

### Adjust Voice Speed/Pitch

Edit `v2/docker-compose.yml`:
```yaml
whisper-stt:
  environment:
    - PIPER_LENGTH_SCALE=0.9  # Faster (0.5-1.5)
```

Restart: `docker compose -f v2/docker-compose.yml up -d whisper-stt`

### Change LLM Model Selection

Router automatically chooses:
- **Fast queries** → Hermes3 (concise, ~2s response)
- **Deep queries** → Qwen3-4B or VL (detailed, ~5-10s)

To force a specific model, edit orchestrator environment in docker-compose.yml.

### Tune Memory Recall

Edit `v2/docker-compose.yml`:
```yaml
orchestrator:
  environment:
    - MEMORY_MIN_SCORE=0.5   # Lower = more recall (0.0-1.0)
    - MEMORY_TOP_K=10        # More memories retrieved
```

Restart: `docker compose -f v2/docker-compose.yml up -d orchestrator`

---

## Monitoring & Control

### HA Dashboard (Optional)

Add memory and router packages to HA:
```bash
# Copy monitoring packages
docker cp v2/ha_config/packages/memory.yaml homeassistant:/config/packages/
docker cp v2/ha_config/packages/router.yaml homeassistant:/config/packages/

# Restart HA
# Settings → System → Restart
```

This adds sensors for:
- Memory hits and recall rate
- VL routing stats
- GPU utilization (if NVML enabled)

### Check Logs

```bash
# Orchestrator (memory, routing decisions)
docker logs -f hassistant_v2_orchestrator

# STT/TTS
docker logs -f hassistant_v2_wyoming_proxy

# Speech backend
docker logs -f hassistant_v2_whisper-stt
```

---

## Troubleshooting

### "No response" or timeout

**Check orchestrator:**
```bash
curl -fsS http://localhost:8020/health
```

**Check Ollama models:**
```bash
docker exec hassistant_v2_ollama_text ollama list
```

Should show: `hermes3:latest`, `qwen3:4b`

### STT not working

**Check Wyoming STT:**
```bash
# From HA terminal or SSH:
nc -zv wyoming-openai 10300
```

Should connect successfully.

**Check whisper-stt backend:**
```bash
curl -fsS http://localhost:8000/health
```

### TTS not working

**Check Wyoming TTS:**
```bash
nc -zv wyoming-openai 10210
```

**Check Piper voice installed:**
```bash
docker exec hassistant_v2_piper_main ls /config
```

Should show `en_US-glados-medium.onnx`

### Memory not recalling

**Check embeddings processed:**
```bash
curl -fsS http://localhost:8010/stats | jq '{total, embedded, pending}'
```

`pending` should be 0.

**Test memory search directly:**
```bash
curl -X POST http://localhost:8010/memory/search \
  -H 'Content-Type: application/json' \
  -d '{"q":"pizza"}' | jq '.results[].text'
```

**Lower recall threshold:**
```bash
curl -X POST http://localhost:8010/config \
  -H 'Content-Type: application/json' \
  -d '{"min_score": 0.5}'
```

---

## Next Steps

1. ✅ Voice assistant working
2. 📱 Install HA Companion app for mobile voice control
3. 🎙️ Set up wake word detection (Porcupine on Pi)
4. 📝 Seed important memories (preferences, facts, schedules)
5. 📊 Add monitoring dashboard
6. 🎯 Create voice-triggered automations

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│            Home Assistant Assist                │
└─────────────────┬───────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌────────┐   ┌────────┐   ┌────────┐
│Wyoming │   │OpenAI  │   │Wyoming │
│  STT   │   │ Chat   │   │  TTS   │
│:10300  │   │Convo   │   │:10210  │
└───┬────┘   └───┬────┘   └────┬───┘
    │            │             │
    ▼            ▼             ▼
┌────────┐   ┌────────┐   ┌────────┐
│Whisper STT│   │ Orch.  │   │Whisper STT│
│Whisper │   │/v1/chat│   │ Piper  │
│ CUDA   │   │:8020   │   │GLaDOS  │
└────────┘   └───┬────┘   └────────┘
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
    ┌──────┐ ┌──────┐ ┌──────┐
    │Memory│ │Router│ │Ollama│
    │:8010 │ │ VL   │ │:11435│
    └──────┘ └──────┘ └──────┘
```

---

## Performance Notes

With your dual GPU setup (GTX 1080 Ti + GTX 1070):

- **STT latency**: ~200-500ms (CUDA Whisper base.en)
- **LLM response**: ~1-3s (Hermes3 fast path)
- **TTS latency**: ~300-600ms (Piper streaming)
- **Total end-to-end**: ~2-4 seconds

Memory retrieval adds ~50-100ms (negligible with caching).

---

## Related Docs

- [Memory System](./MEMORY.md) - Memory architecture and API
- [Router](../ha_config/packages/router.yaml) - Intelligent model selection
- [Speech Stack](../ha_config/packages/speech.yaml) - STT/TTS configuration
