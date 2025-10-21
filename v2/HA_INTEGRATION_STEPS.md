# Home Assistant Integration Steps

Complete these steps in the Home Assistant UI to finish Step 1 green-light checklist.

---

## Prerequisites

✅ Speaches stack running and healthy
✅ HA monitoring package created (`ha_config/packages/speech.yaml`)
✅ Wyoming endpoints exposed:
  - STT: Port 10300 (TCP)
  - TTS: Port 10210 (TCP)

---

## Step 1: Restart Home Assistant

The `speech.yaml` package was just added. Restart HA to load it:

```
Settings → System → Restart Home Assistant
```

**Wait 1-2 minutes** for restart.

---

## Step 2: Verify Monitoring Sensors

After restart, check that new entities appear:

```
Settings → Devices & Services → Entities
```

Search for "whisper" - you should see:
- ✅ `sensor.whisper_stt_health`
- ✅ `sensor.whisper_stt_latency`

Search for "wyoming" - confirm:
- ✅ `binary_sensor.wyoming_proxy_health`
- ✅ `switch.tts_fallback_wyoming_piper`

**Troubleshooting:**
- If entities don't appear, check HA logs: `Settings → System → Logs`
- Common issue: Wrong hostname (should be `hassistant_v2_whisper_stt` if HA is on `assistant_default` network)
- If HA can't reach whisper-stt, use host IP instead: `192.168.2.13:8000`

---

## Step 3: Add Wyoming STT Integration

```
Settings → Devices & Services → Add Integration
```

1. Search for "**Wyoming Protocol**"
2. Click "Wyoming Protocol"
3. Configure STT:
   - **Host**: `192.168.2.13` (or use container name if on same network)
   - **Port**: `10300`

4. Click "Submit"
5. Integration should show as "Wyoming Protocol" with STT capability

---

## Step 4: Add Wyoming TTS Integration

Repeat for TTS:

```
Settings → Devices & Services → Add Integration → Wyoming Protocol
```

1. Configure TTS:
   - **Host**: `192.168.2.13`
   - **Port**: `10210`

2. Click "Submit"
3. Integration should show as "Wyoming Protocol" with TTS capability

**Note:** You'll now have TWO Wyoming integrations:
- One for STT (port 10300)
- One for TTS (port 10210)

---

## Step 5: Configure Assist Pipeline

```
Settings → Voice Assistants → Assist
```

1. Click "**Add Assistant**" or edit existing
2. Configure pipeline:
   - **Conversation Agent**: (your preferred - Ollama, Conversation, etc.)
   - **Speech-to-Text**: Select "Wyoming Protocol" (port 10300)
   - **Text-to-Speech**: Select "Wyoming Protocol" (port 10210)
   - **Wake Word**: (optional - your wake word device if any)

3. Click "Create" or "Update"
4. Set as **default pipeline** if desired

---

## Step 6: Test Voice Pipeline (Green-Light Checklist #5)

**Test latency with long paragraph:**

1. Open HA Voice Assistant (top-right microphone icon)
2. Click microphone and speak a **long paragraph** (100+ words), for example:

   > "The quick brown fox jumps over the lazy dog. This is a test of the speech processing system. We are measuring latency from the moment I stop speaking until the first audio chunk is returned. The system should begin playing audio within five hundred milliseconds. This paragraph contains approximately one hundred words to properly test the streaming capabilities of the text to speech engine. If everything is working correctly, you should hear this audio start playing very quickly without waiting for the entire sentence to be processed."

3. **Measure latency:**
   - **Start timer** when you stop speaking
   - **Stop timer** when you hear first audio
   - **Target**: < 500ms (streaming L16)
   - **Acceptable**: < 700ms (if HA forces WAV conversion)

4. **Check monitoring:**
  ```
  Developer Tools → States
  ```
  - Check `sensor.whisper_stt_latency` value

---

## Step 7: Create Dashboard (Optional)

Add monitoring card to a dashboard:

```yaml
type: entities
title: Speech Stack Monitor
entities:
  - entity: sensor.whisper_stt_health
  - entity: sensor.whisper_stt_latency
  - entity: binary_sensor.wyoming_proxy_health
  - entity: switch.tts_fallback_wyoming_piper
```

Or use History Graph for latency trends:

```yaml
type: history-graph
title: Speech Latency
entities:
  - entity: sensor.whisper_stt_latency
hours_to_show: 24
refresh_interval: 30
```

---

## Troubleshooting

### Wyoming integration fails to connect

**Check network connectivity (Wyoming uses raw TCP, so use netcat):**
```bash
# From HA container or host:
nc -zv 192.168.2.13 10300
nc -zv 192.168.2.13 10210
```

**Check Wyoming proxy is healthy:**
```bash
curl http://192.168.2.13:8080/healthz
```

**Expected output:**
```json
{
  "ok": true,
  "asr": "http://whisper-stt:8000/v1/audio/transcriptions",
  "tts": "tcp://piper-main:10200",
  "primary_tts_host": "piper-main",
  "primary_tts_port": 10200,
  ...
}
```

### Sensors show "unavailable"

**Check HA can reach whisper-stt:**
```bash
# From HA container:
curl http://hassistant_v2_whisper_stt:8000/health
```

If fails, update `/ha_config/packages/speech.yaml`:
- Replace `hassistant_v2_whisper-stt` with `192.168.2.13`
- Restart HA

### High latency (> 1 second)

**Check GPU is being used:**
```bash
nvidia-smi
# Should show python3.9 process on GPU1
```

**Check whisper-stt health:**
```bash
curl http://192.168.2.13:8000/health
```

Expected: `"device": "cuda"`

If shows `"device": "cpu"`, GPU isn't working - check driver/CUDA setup.

### TTS is garbled/wrong

**Check Piper voice files**
```
docker exec -it hassistant_v2_piper_main ls /config
```
Ensure the desired `*.onnx` + `.onnx.json` voice pair exists (default: `en_US-glados-medium`).

**Force container reload after updating voices**
```
docker compose -f v2/docker-compose.yml restart piper-main
```

**Adjust speaking cadence (optional)**
- Set `PIPER_LENGTH` env var (e.g. `0.9` faster, `1.1` slower)
- Restart `piper-main` afterwards

---

## Green-Light Checklist Completion

After completing these steps, verify:

- ✅ `docker compose up -d` speech stack healthy (`whisper-stt`, `piper-main`, `wyoming_openai`)
- ✅ `nvidia-smi` shows GPU load on STT
- ✅ `smoke_tts_stream.sh` passes (L16 header)
- ✅ HA shows: Whisper STT Health, STT Latency, `binary_sensor.wyoming_proxy_health`, `switch.tts_fallback_wyoming_piper`
- ✅ Long paragraph via HA < 500ms first-chunk latency

**Document results in:** `v2/STEP1_COMPLETE.md`

---

## Next Steps

Once green-light checklist is complete:

1. **Memory Integration** (Step 2): Letta-bridge + pgvector
2. **TTS Enhancements**: Expand Piper voice options and tuning
3. **Orchestrator v2**: Tool provider with memory/HA skills
4. **Production Hardening**: Monitoring, logging, error handling
