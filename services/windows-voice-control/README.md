# Windows Voice Control - Dockerized

Containerized Windows Voice Control client that sends commands to Windows laptops via audio cable and Piper TTS.

## Quick Start

### 1. Enable the service

The service uses a Docker Compose profile to keep it optional. Enable it with:

```bash
# Start just the windows-voice-control service
docker compose --profile windows-control up -d windows-voice-control

# Or start all services including windows-control
docker compose --profile windows-control up -d
```

### 2. Send a test command

```bash
# Using docker exec
docker exec hassistant-windows-voice-control \
  python3 windows_voice_control.py "Open Notepad"

# Type text
docker exec hassistant-windows-voice-control \
  python3 windows_voice_control.py --type "Hello from Docker"

# Send keystrokes
docker exec hassistant-windows-voice-control \
  python3 windows_voice_control.py --key Enter
```

### 3. Test audio device

```bash
docker exec hassistant-windows-voice-control \
  python3 windows_voice_control.py --test
```

## Architecture

```
┌──────────────────────────────────┐
│  Windows Voice Control Container │
│  - Python client script          │
│  - ALSA/PulseAudio audio tools   │
└───────────┬──────────────────────┘
            │ Wyoming Protocol (10200)
            ↓
┌──────────────────────────────────┐
│  Piper TTS (hassistant-piper-    │
│  glados)                          │
│  - GLaDOS voice synthesis        │
└───────────┬──────────────────────┘
            │ WAV audio
            ↓
┌──────────────────────────────────┐
│  USB Audio Device (/dev/snd)     │
│  - Passed through from host      │
└───────────┬──────────────────────┘
            │ 3.5mm audio cable
            ↓
┌──────────────────────────────────┐
│  Windows Laptop                   │
│  - Microphone input              │
│  - Windows Voice Assistant       │
└──────────────────────────────────┘
```

## Configuration

All configuration is via environment variables in `.env` or `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_URL` | `http://hassistant-piper-glados:10200` | Piper TTS service URL |
| `PIPER_HOST` | `hassistant-piper-glados` | Piper hostname |
| `USB_AUDIO_DEVICE` | `hw:1,0` | ALSA audio device (use `aplay -l` in container) |
| `USE_PULSEAUDIO` | `false` | Use PulseAudio instead of ALSA |
| `WYOMING_ENABLED` | `false` | Use Wyoming protocol directly |
| `USE_DIRECT_PIPER` | `false` | Use direct Piper command (not available in container) |

## Audio Device Setup

The container passes through `/dev/snd` from the host. To find your USB audio device:

```bash
# List audio devices inside container
docker exec hassistant-windows-voice-control aplay -l

# Example output:
# card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
#   Subdevices: 1/1
#   Subdevice #0: subdevice #0

# Set USB_AUDIO_DEVICE=hw:1,0 for card 1, device 0
```

## Troubleshooting

### Audio not playing

```bash
# Check if audio device is accessible
docker exec hassistant-windows-voice-control aplay -l

# Check if container has permission
docker exec hassistant-windows-voice-control ls -la /dev/snd

# Test with a beep
docker exec hassistant-windows-voice-control \
  speaker-test -t sine -f 1000 -c 2 -D hw:1,0 -l 1
```

### Piper TTS not reachable

```bash
# Check if Piper is running
docker ps | grep piper

# Test connectivity from container
docker exec hassistant-windows-voice-control \
  curl -v http://hassistant-piper-glados:10200/
```

### Wyoming protocol timeout

The Wyoming protocol on port 10200 is a binary protocol, not HTTP. The container uses it correctly via the Wyoming client.

## Development

### Rebuild the container

```bash
docker compose build windows-voice-control
docker compose --profile windows-control up -d windows-voice-control
```

### Check logs

```bash
docker logs -f hassistant-windows-voice-control
```

### Run interactively

```bash
docker compose run --rm windows-voice-control bash

# Inside container:
python3 windows_voice_control.py "Open Notepad"
aplay -l
```

## Integration Examples

### From Home Assistant automation

```yaml
automation:
  - alias: "Windows Voice Command"
    trigger:
      - platform: state
        entity_id: input_boolean.windows_command_trigger
        to: "on"
    action:
      - service: shell_command.windows_voice
        data:
          command: "{{ states('input_text.windows_command') }}"
```

### From command line

```bash
# Simple command
docker exec hassistant-windows-voice-control \
  python3 windows_voice_control.py "Open Chrome"

# With error handling
if docker exec hassistant-windows-voice-control \
  python3 windows_voice_control.py "Open Notepad"; then
  echo "✅ Command sent successfully"
else
  echo "❌ Command failed"
fi
```

## Why Containerize?

**Benefits:**
- ✅ Clean Docker network resolution (no localhost confusion)
- ✅ Consistent environment (Python deps, audio tools)
- ✅ Easy deployment (single `docker compose up`)
- ✅ Isolated audio device access
- ✅ Service dependencies managed automatically

**vs. Host-based execution:**
- ❌ Manual Python dependency management
- ❌ Localhost/container name confusion
- ❌ Different audio tooling per distro
- ❌ Manual service startup
