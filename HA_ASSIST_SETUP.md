# Home Assistant Assist Pipeline Setup for GLaDOS

Complete guide to setting up voice interaction with GLaDOS using HA's native Assist pipeline.

## Architecture Overview

```
Wake Word → HA Assist API → Wyoming STT (Whisper) → Ollama (Hermes3) → Wyoming TTS (Piper GLaDOS) → Speaker
```

**Everything runs in Home Assistant** - no custom services needed!

---

## Step 1: Install Whisper (STT)

1. Go to **Settings → Add-ons → Add-on Store**
2. Search for **"Whisper"** or **"faster-whisper"**
3. Click **Install**
4. **Configuration**:
   - Model: `base` or `small` (good balance of speed/accuracy)
   - Language: `en`
5. Click **Start** and enable **Start on boot**

---

## Step 2: Install Piper (TTS)

1. Go to **Settings → Add-ons → Add-on Store**
2. Search for **"Piper"**
3. Click **Install**
4. **Don't start it yet** - need to add GLaDOS voice first

### Adding GLaDOS Voice to Piper

Piper doesn't include GLaDOS by default. You have two options:

#### Option A: Use Piper's Built-in Voices (Quick)
Choose a voice similar to GLaDOS:
- `en_US-amy-medium` (female, slightly robotic)
- `en_GB-alba-medium` (British accent, GLaDOS-esque)

#### Option B: Custom GLaDOS Voice (Better!)
You already have the GLaDOS ONNX model. Add it to Piper:

1. Go to **Add-on Configuration** for Piper
2. Under **Network**, note the port (usually `10200`)
3. Copy your GLaDOS model to HA:
   ```bash
   # From your main server:
   docker cp /home/qjaq/assistant/models/tts/en_US-glados-high.onnx homeassistant:/config/piper/
   docker cp /home/qjaq/assistant/models/tts/en_US-glados-high.onnx.json homeassistant:/config/piper/
   ```

4. Start the Piper add-on
5. It will auto-detect the GLaDOS voice

---

## Step 3: Configure Assist Pipeline

1. Go to **Settings → Voice Assistants → Assist**
2. Click **Add Assistant** or edit the default one
3. Configure:

### Conversation
- **Conversation Agent**: `GLaDOS Hermes` (the Ollama agent you created)

### Speech-to-Text
- **Speech-to-Text**: `faster-whisper` or `whisper`
- **Language**: `en`

### Text-to-Speech
- **Text-to-Speech**: `piper`
- **Voice**:
  - `en_US-glados-high` (if you added custom GLaDOS)
  - `en_US-amy-medium` (or another voice as fallback)
- **Speed**: `1.0` (normal speed)

### Wake Word (Optional - for direct HA hardware)
- Leave this **disabled** if using Pi with Porcupine
- Or use **"Ok Nabu"** for testing with HA hardware

4. Click **Update** to save

---

## Step 4: Test the Pipeline

### Test in HA UI
1. Go to **Settings → Voice Assistants**
2. Click **Assist**
3. Click the microphone icon
4. Say: *"Turn on the living room lights"*
5. You should hear GLaDOS respond!

### Test via API (for Pi client)
```bash
# Get your HA token from: Profile → Long-Lived Access Tokens
HA_URL="http://assistant-ha:8123"
HA_TOKEN="your_token_here"

# Test conversation
curl -X POST "$HA_URL/api/conversation/process" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "What time is it?"}'
```

---

## Step 5: Configure Pi Client

The Pi client will use **HA's Assist API** which handles everything:

1. Edit Pi configuration:
   ```bash
   nano ~/.env
   ```

2. Set values:
   ```env
   PV_ACCESS_KEY=your_picovoice_key
   HA_URL=http://glad0s:8123
   HA_TOKEN=your_ha_token
   WAKE_WORD_MODEL=computer
   ```

3. The Pi client sends audio to HA, and HA:
   - Transcribes with Whisper
   - Processes with Ollama
   - Responds with Piper (GLaDOS voice)
   - Returns audio to Pi

---

## Advanced: Custom GLaDOS Voice Training

If you want an even better GLaDOS voice:

1. Use **Piper Training** to fine-tune on GLaDOS audio clips
2. Or use **Tortoise TTS** for higher quality (slower)
3. Or integrate **Bark** for more expressive speech

---

## Troubleshooting

### "No TTS voice available"
- Check Piper add-on is running: **Settings → Add-ons → Piper → Running**
- Verify voice files exist in `/config/piper/`
- Check Piper logs for errors

### "Speech not recognized"
- Check Whisper add-on is running
- Test microphone input levels
- Try a different Whisper model (`tiny`, `base`, `small`)

### "Ollama not responding"
- Verify Ollama container is running: `docker ps | grep ollama`
- Check Ollama models are loaded: `docker exec ollama-chat ollama list`
- Test Ollama directly: `curl http://localhost:11434/api/tags`

### "Wrong voice used"
- Go to **Settings → Voice Assistants → Assist**
- Verify correct TTS voice is selected
- Restart Piper add-on if you just added GLaDOS voice

---

## Next Steps

1. ✅ Complete Assist pipeline setup
2. 📱 Install HA mobile app for voice control anywhere
3. 🎙️ Set up Pi client for wake word voice interaction
4. 📅 Add Google Calendar for context-aware responses
5. 🏠 Create voice-triggered automations
6. 🎵 Integrate Spotify for music control via voice

---

## Performance Notes

- **Whisper** uses CPU by default (can use GPU with configuration)
- **Piper** is very fast even on CPU
- **Ollama** uses your GPUs (configured in docker-compose)
- **End-to-end latency**: ~2-4 seconds for full voice interaction

Your setup with GTX 1080 Ti + GTX 1070 will handle this easily!
