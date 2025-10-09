# Wyoming Protocol Setup - Now Working!

## ✅ Services Running

Your Wyoming services are UP and listening:
- **Whisper** (STT): `172.18.0.6:10300` or `hassistant-whisper:10300`
- **Piper** (TTS): `172.18.0.5:10200` or `hassistant-piper-glados:10200`

**Note:** Wyoming protocol is WebSocket-based, NOT HTTP, so `curl` won't work - this is expected!

---

## 🎯 Add to Home Assistant (Do This Now!)

### Step 1: Add Whisper Integration

1. Open **Home Assistant** web UI
2. Go to **Settings** → **Devices & Services**
3. Click **+ ADD INTEGRATION** (bottom right)
4. Search for: **"Wyoming Protocol"**
5. Click on it
6. Configure:
   ```
   Host: 172.18.0.6
   Port: 10300
   ```
   OR (if DNS works):
   ```
   Host: hassistant-whisper
   Port: 10300
   ```
7. Click **SUBMIT**
8. You should see: **"Wyoming Protocol"** added with a Whisper icon

---

### Step 2: Add Piper Integration

1. **Settings** → **Devices & Services**
2. Click **+ ADD INTEGRATION**
3. Search for: **"Wyoming Protocol"**
4. Click on it
5. Configure:
   ```
   Host: 172.18.0.5
   Port: 10200
   ```
   OR:
   ```
   Host: hassistant-piper-glados
   Port: 10200
   ```
6. Click **SUBMIT**
7. You should see: **"Wyoming Protocol"** added with a Piper/speaker icon

---

### Step 3: Configure Assist Pipeline

1. Go to **Settings** → **Voice Assistants**
2. Click **Assist** (or **Add Assistant** if you don't have one)
3. Configure each section:

   **Conversation:**
   - Select: `GLaDOS Hermes` (your Ollama conversation agent)

   **Speech-to-text:**
   - Select: `faster-whisper` or the Whisper integration you just added
   - Language: `en`

   **Text-to-speech:**
   - Select: `piper` or the Piper integration you just added
   - Voice: `en_US-amy-medium`
   - Speed: `1.0`

   **Wake word:**
   - Leave as `None` (we'll use Porcupine on Pi)

4. Click **UPDATE**

---

## 🧪 Test It!

### Quick Test in HA UI

1. Go to **Settings** → **Voice Assistants**
2. You should see **Assist** configured
3. Click the **microphone button** (if available)
4. OR go to **Developer Tools** → **Services**
5. Call service: `conversation.process`
   ```yaml
   service: conversation.process
   data:
     text: "What time is it?"
   ```

---

## 🔧 Troubleshooting

### "Could not connect to Wyoming Protocol"

**Try using IP addresses instead of hostnames:**
- Whisper: `172.18.0.6:10300`
- Piper: `172.18.0.5:10200`

### "Integration not found"

Make sure you're searching for **"Wyoming Protocol"** exactly (not "Whisper" or "Piper").

### "No response from services"

Check services are running:
```bash
docker ps | grep hassistant
docker logs hassistant-whisper --tail 20
docker logs hassistant-piper-glados --tail 20
```

Both should show: `INFO:__main__:Ready`

---

## 📊 Your Complete Stack

```
┌─────────────────────┐
│   Home Assistant    │
│   (Main Hub)        │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌─────────┐ ┌─────────┐
│ Whisper │ │  Piper  │
│  (STT)  │ │  (TTS)  │
│  :10300 │ │  :10200 │
└─────────┘ └─────────┘
          │
          ▼
    ┌──────────┐
    │  Ollama  │
    │ (LLM AI) │
    │  :11434  │
    └──────────┘
```

---

## 🎉 Next Steps

1. ✅ Wyoming services running
2. 🔲 Add integrations in HA UI (**do this now!**)
3. 🔲 Configure Assist pipeline
4. 🔲 Test voice interaction
5. 🔲 Deploy Pi client for wake word

**You're almost there!** Just add the integrations in HA and you'll have a fully working voice assistant.
