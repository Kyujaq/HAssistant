# Where to Find GLaDOS Voice in Home Assistant

## Important: Voice Selection is in TWO Places!

### 1. When Adding Wyoming Piper Integration
**You WON'T see voice options here** - it just connects to the service.
- Settings → Devices & Services → + ADD INTEGRATION
- Wyoming Protocol
- Host: `172.18.0.5` or `hassistant-piper`
- Port: `10200`
- ✅ This just adds the connection - NO voice picker yet!

---

### 2. When Configuring Assist Pipeline ⭐ **THIS IS WHERE YOU SELECT GLADOS**

1. Go to **Settings** → **Voice Assistants** → **Assist**
2. Click your assistant or **Add Assistant**
3. Scroll to **Text-to-Speech** section
4. Click the dropdown under **Text-to-speech**
5. Select your Piper integration
6. **NOW you'll see voice options!**
7. Look for: `en_US-glados-high` ← **THIS IS IT!**

---

## If You Don't See en_US-glados-high:

### Option A: It might show as default already
The Piper container is configured with `--voice en_US-glados-high` by default, so it might just use it automatically.

### Option B: Restart the Piper integration in HA
1. Settings → Devices & Services
2. Find **Wyoming Protocol** (the Piper one on port 10200)
3. Click the **3 dots** → **Reload**
4. Go back to Assist configuration - voice should appear

### Option C: Check available voices via command
```bash
# See what Piper reports as available
docker logs hassistant-piper 2>&1 | grep -i voice
```

---

## Quick Test Without HA UI

Test GLaDOS voice directly:

```bash
# Test Piper with GLaDOS voice
docker exec hassistant-piper /usr/share/piper/piper \
  --model /data/en_US-glados-high.onnx \
  --output_file /tmp/test.wav \
  "Hello, this is GLaDOS speaking"

# Copy out and play
docker cp hassistant-piper:/tmp/test.wav /tmp/glados-test.wav
aplay /tmp/glados-test.wav
```

---

## What You Should See in HA Assist Config:

```
Text-to-Speech
├─ Text-to-speech: [Dropdown]
│  └─ Select: Wyoming Protocol (Piper)
│
└─ After selecting Piper:
   ├─ Voice: [Dropdown will appear]
   │  ├─ en_US-amy-medium     ← Default fallback
   │  └─ en_US-glados-high    ← **YOUR GLADOS VOICE!**
   │
   ├─ Speed: [Slider] 1.0
   └─ Other TTS options...
```

---

## Why It Might Not Show Up:

1. **HA cache**: Restart HA Core or reload the integration
2. **File permissions**: Already correct (we see the files)
3. **Piper not scanning /data**: Fixed with `--data-dir /data`
4. **Voice name mismatch**: We're using exact name `en_US-glados-high`

---

## Current Piper Configuration:

Your Piper is running with:
```bash
--voice en_US-glados-high          # Default voice
--uri 'tcp://0.0.0.0:10200'         # Wyoming protocol
--data-dir /data                    # Where voices are
--piper /usr/share/piper/piper      # Piper executable
```

Voices available in `/data/`:
- ✅ `en_US-glados-high.onnx` (55MB) - **GLaDOS!**
- ✅ `en_US-amy-medium.onnx` (61MB) - Fallback

---

## Next Steps:

1. ✅ Add Wyoming Piper integration (no voice picker here)
2. ⭐ Go to **Settings → Voice Assistants → Assist**
3. ⭐ Configure **Text-to-Speech** section
4. ⭐ Select Piper, THEN pick voice: **en_US-glados-high**
5. 🎉 Test and hear GLaDOS!

If `en_US-glados-high` still doesn't appear, the Piper container is configured to USE it as default anyway, so you'll get GLaDOS voice even if you select "piper" with no explicit voice choice!
