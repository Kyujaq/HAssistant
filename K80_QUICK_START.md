# K80 Vision Integration - Quick Start Guide

## Current Status: Ready for Model Download

Your Tesla K80 GPU is integrated and ready to use! Just need to download model weights.

---

## Quick Start (3 Steps)

### 1. Download Model Weights

```bash
cd /home/qjaq/HAssistant/services/vision-gateway
./download_models.sh
```

This downloads ~700MB of GroundingDINO model files.

### 2. Enable K80

Edit `docker-compose.yml`:

```yaml
environment:
  - K80_ENABLED=true  # Change this line from false to true
```

### 3. Restart Service

```bash
docker compose restart vision-gateway
```

---

## Verify It's Working

Watch for K80 logs:

```bash
docker compose logs -f vision-gateway | grep -i k80
```

You should see:
```
[hdmi] Initializing K80 preprocessor on cuda:2...
INFO:app.k80_preprocessor:Using GPU 2: Tesla K80
INFO:app.k80_preprocessor:GroundingDINO model loaded successfully
[hdmi] K80 preprocessor initialized successfully!
```

Then watch for detections:
```bash
docker compose logs -f vision-gateway | grep "K80 Detection"
```

---

## What You Get

- **Continuous Detection**: K80 scans for buttons, dialogs, windows at 5-10 FPS
- **Smart Triggering**: Qwen VL only called when scene changes (10x fewer calls)
- **Any UI Element**: Detects buttons, dialogs, text fields, windows automatically
- **HA Integration**: Scene changes sent as `vision.k80_scene_change` events

---

## Configuration

Tune detection sensitivity in `docker-compose.yml`:

```yaml
- K80_BOX_THRESHOLD=0.35         # Lower = more detections (try 0.25-0.45)
- K80_TEXT_THRESHOLD=0.25        # Lower = more text matches
- K80_SCENE_CHANGE_THRESHOLD=0.3 # Lower = more sensitive (more Qwen calls)
```

---

## Troubleshooting

**Models not found?**
```bash
./services/vision-gateway/download_models.sh
```

**K80 not working?**
```bash
# Check GPU is visible
docker exec vision-gateway python3 -c "import torch; print(torch.cuda.get_device_name(2))"

# Should print: Tesla K80
```

**Need help?**
See full docs: `docs/implementation/K80_INTEGRATION_COMPLETE.md`

---

## Architecture Summary

```
GPU 0 (1080 Ti): Qwen vision model for deep analysis
GPU 1 (1070):    Hermes-3 chat + Whisper STT + Piper TTS
GPU 2 (K80):     GroundingDINO continuous detection ← NEW!
```

The K80 watches your screen continuously and only calls the heavy Qwen model when something interesting changes!

---

**That's it!** Download models, enable K80, restart. You're done! 🎉
