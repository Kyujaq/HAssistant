# GLaDOS Voice Assistant - Quick Start Guide

Complete setup in under 10 minutes!

## ✅ Current Status

You have:
- ✅ **Ollama** running with glados-hermes3 + glados-qwen models
- ✅ **Wyoming Whisper** (STT) on port 10300
- ✅ **Wyoming Piper** (TTS) on port 10200
- ✅ **Home Assistant** running

## 🎯 Next Steps

### 1. Add Wyoming Services to Home Assistant (5 min)

#### Add Whisper (Speech-to-Text)
1. Open **Home Assistant** → **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Wyoming Protocol"**
4. Configure:
   - **Host**: `hassistant-whisper` (or `glad0s` or your server IP)
   - **Port**: `10300`
5. Click **Submit**
6. You should see **"Wyoming Protocol - Whisper"** added

#### Add Piper (Text-to-Speech)
1. **Settings** → **Devices & Services** → **+ Add Integration**
2. Search for **"Wyoming Protocol"**
3. Configure:
   - **Host**: `hassistant-piper` (or `glad0s` or your server IP)
   - **Port**: `10200`
4. Click **Submit**
5. You should see **"Wyoming Protocol - Piper"** added

---

### 2. Configure Assist Pipeline (3 min)

1. Go to **Settings** → **Voice Assistants** → **Assist**
2. Click your assistant (or **Add Assistant**)
3. Configure:

   - **Name**: `GLaDOS`

   - **Conversation agent**: `GLaDOS Hermes` (the Ollama conversation agent)

   - **Speech-to-text**: `faster-whisper` or `whisper`

   - **Text-to-speech**: `piper`
     - **Voice**: `en_US-amy-medium` (closest to GLaDOS for now)
     - **Speed**: `1.0`

   - **Wake word**: `None` (we'll use Porcupine on Pi)

4. Click **Update**

---

### 3. Test Voice Interaction (2 min)

#### Test in HA UI
1. Go to **Settings** → **Voice Assistants** → **Assist**
2. Click the **microphone icon**
3. Say: *"What time is it?"*
4. You should hear a response!

#### Test via curl (debug)
```bash
# From your server
curl -X POST "http://assistant-ha:8123/api/conversation/process" \
  -H "Authorization: Bearer YOUR_HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Turn on the living room lights"}'
```

---

### 4. Deploy to Raspberry Pi (Optional - for voice everywhere)

See `PI_SETUP.md` for full instructions.

**Quick version:**
```bash
# On Pi
sudo apt install python3-pip portaudio19-dev
pip install pvporcupine pyaudio requests numpy

# Copy client
scp user@glad0s:/home/qjaq/HAssistant/pi_client.py ~/
scp user@glad0s:/home/qjaq/HAssistant/pi_client.env.example ~/.env

# Configure .env with your tokens
nano ~/.env

# Run
python3 ~/pi_client.py
```

Say **"Computer"** → speak your command → GLaDOS responds!

---

## 🔧 Troubleshooting

### "No speech-to-text integration found"
```bash
# Check Whisper is running
docker logs hassistant-whisper --tail 20

# Test Whisper directly
curl http://localhost:10300
```

### "No text-to-speech integration found"
```bash
# Check Piper is running
docker logs hassistant-piper --tail 20

# Test Piper directly
curl "http://localhost:10200/api/tts?text=Hello%20world"
```

### "Conversation agent not responding"
```bash
# Check Ollama
docker logs hassistant-ollama --tail 20

# List models
docker exec hassistant-ollama ollama list

# Test Ollama
curl http://localhost:11434/api/tags
```

### HA can't connect to Wyoming services
- Use IP address instead of hostname: `192.168.x.x:10300`
- Check all containers are on same network: `docker network inspect assistant_default`
- Verify ports are accessible: `curl http://glad0s:10300`

---

## 📊 Architecture Diagram

```
┌─────────────┐
│ Raspberry Pi│
│   (Wake    │
│   Word)    │──┐
└─────────────┘  │
                 │
                 ▼
        ┌────────────────┐
        │ Home Assistant │
        │   (Ollama)     │◄──── Conversation
        └────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌───────────────┐  ┌──────────────┐
│   Whisper     │  │    Piper     │
│   (STT)       │  │    (TTS)     │
│ Port 10300    │  │ Port 10200   │
└───────────────┘  └──────────────┘
```

---

## 🚀 What You Can Do Now

### Voice Commands
- *"Turn on the lights"*
- *"What's the weather like?"*
- *"Set living room to 72 degrees"*
- *"What's on my calendar today?"* (after adding Google Calendar)

### Automations
- Morning briefings
- Context-aware scenes
- Smart reminders
- Email drafting
- Calendar intelligence

See `examples/` directory for automation templates!

---

## 🎯 Next Level

1. **Add Google Calendar** - Get calendar-aware responses
2. **Custom GLaDOS voice** - Train better Piper voice
3. **Create automations** - Morning briefings, reminders, etc.
4. **Mobile app** - Use HA Companion app for voice anywhere
5. **Node-RED** - Visual automation programming
6. **Windows Voice Control** - Control Windows laptop via audio cable (see [WINDOWS_VOICE_ASSIST_SETUP.md](WINDOWS_VOICE_ASSIST_SETUP.md))

---

## 📝 Summary

You now have:
- 🎤 **Voice input** via Whisper STT
- 🧠 **AI brain** via Ollama (local, GPU-accelerated)
- 🔊 **Voice output** via Piper TTS
- 🏠 **Smart home control** via Home Assistant
- 💻 **Computer control** via vision-based agent
- 🪟 **Windows control** via audio cable (optional)
- 🔒 **100% local** - no cloud dependencies

**All running on your own hardware with your GPUs!**

Congratulations - you have a fully functional GLaDOS voice assistant! 🎉
