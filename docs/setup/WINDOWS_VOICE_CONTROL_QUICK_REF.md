# Windows Voice Control - Quick Reference

Quick commands and setup for controlling Windows via audio cable.

## Quick Setup (5 minutes)

### 1. Hardware Setup
```bash
# Connect: Linux USB Dongle (3.5mm out) → Aux Cable → Windows Headset Port
```

### 2. Find Your USB Audio Device
```bash
# List audio devices
aplay -l

# Example output:
# card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
# Your device is: hw:1,0
```

### 3. Test Audio Output
```bash
# Test with a beep
speaker-test -D hw:1,0 -c 2 -t wav

# Test with a sound file
aplay -D hw:1,0 /usr/share/sounds/alsa/Front_Center.wav
```

### 4. Configure Environment
```bash
# Copy example config
cp config/windows_voice_control.env.example .env

# Edit your USB device
echo "USB_AUDIO_DEVICE=hw:1,0" >> .env

# Enable clearer voice for Windows (recommended)
echo "USE_DIRECT_PIPER=true" >> .env

# Load environment
source .env
```

### 5. Test Voice Control
```bash
# Simple test (assuming Piper TTS is running)
python3 windows_voice_control.py "Open Notepad"
```

## Common Commands

### Voice Clarity (Recommended Setup)
For best results with Windows Voice Assistant, use the clearer kathleen-high voice:
```bash
# In .env file:
USE_DIRECT_PIPER=true
PIPER_VOICE_MODEL=en_US-kathleen-high
PIPER_LENGTH_SCALE=1.1  # 10% slower for better recognition
PIPER_VOLUME_BOOST=1.0  # Increase to 1.2 or 1.5 if needed
```

This provides clearer speech than the default GLaDOS voice, reducing Windows Voice Assistant misunderstandings.

### Application Control
```bash
python3 windows_voice_control.py "Open Notepad"
python3 windows_voice_control.py "Open Excel"
python3 windows_voice_control.py "Open Chrome"
python3 windows_voice_control.py "Close Window"
```

### Text Input
```bash
python3 windows_voice_control.py --type "Hello World"
python3 windows_voice_control.py --type "user@example.com"
```

### Keyboard Actions
```bash
python3 windows_voice_control.py --key Enter
python3 windows_voice_control.py --key Tab
python3 windows_voice_control.py --key Escape
```

### Combined Actions (Automation)
```bash
# Open Notepad and type a message
python3 windows_voice_control.py "Open Notepad"
sleep 2
python3 windows_voice_control.py --type "Meeting notes from $(date)"
python3 windows_voice_control.py --key Enter
```

## Windows Setup

### Enable Voice Access (Windows 11)
1. Settings → Accessibility → Voice Access
2. Toggle "Voice Access" ON
3. Complete voice training
4. Set microphone to headset port

### Enable Cortana (Windows 10)
1. Settings → Cortana
2. Enable "Hey Cortana"
3. Set microphone to headset port

### Configure Microphone
1. Right-click speaker icon → Sounds
2. Recording tab → Select headset microphone
3. Set as Default
4. Properties → Levels → Set boost to +20dB or +30dB

## Troubleshooting

### No sound from USB dongle
```bash
# Check device exists
aplay -l

# Test directly
speaker-test -D hw:1,0 -c 2

# Check volume
amixer -c 1 sget PCM
amixer -c 1 set PCM 100%
```

### Windows doesn't hear commands
1. Check Windows microphone input levels (should show activity)
2. Increase microphone boost in Windows sound settings
3. Ensure cable is in headset port (not line-in)
4. Disable mic enhancements in Windows

### Commands not executing
1. Ensure Windows Voice Assistant is enabled and listening
2. Re-train Voice Access with actual TTS audio
3. Check volume levels on both sides
4. **Use clearer voice**: Set `USE_DIRECT_PIPER=true` for kathleen-high voice
5. **Slow down speech**: Increase `PIPER_LENGTH_SCALE` to 1.2 or 1.3
6. **Boost volume**: Set `PIPER_VOLUME_BOOST=1.5` (requires sox or ffmpeg)

## Integration with Home Assistant

### Shell Command
Add to `configuration.yaml`:
```yaml
shell_command:
  windows_voice: "python3 /path/to/windows_voice_control.py '{{ command }}'"
```

### Automation
```yaml
automation:
  - alias: "Windows Voice Control"
    trigger:
      platform: conversation
      command:
        - "tell windows to [action]"
    action:
      - service: shell_command.windows_voice
        data:
          command: "{{ trigger.slots.action }}"
```

### Usage
Say: "Hey GLaDOS, tell Windows to open Notepad"

## Advanced: Batch Commands

Create a script `batch_commands.sh`:
```bash
#!/bin/bash
# Open Excel and create a simple spreadsheet

python3 windows_voice_control.py "Open Excel"
sleep 3
python3 windows_voice_control.py --type "Budget 2024"
sleep 0.5
python3 windows_voice_control.py --key Tab
python3 windows_voice_control.py --type "1000"
sleep 0.5
python3 windows_voice_control.py --key Enter
```

Run:
```bash
chmod +x batch_commands.sh
./batch_commands.sh
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USB_AUDIO_DEVICE` | `hw:1,0` | ALSA device for USB dongle |
| `TTS_URL` | `http://localhost:10200` | Piper TTS service URL |
| `USE_PULSEAUDIO` | `false` | Use PulseAudio instead of ALSA |
| `PULSEAUDIO_SINK` | - | PulseAudio sink name |
| `USE_DIRECT_PIPER` | `false` | Use direct Piper for clearer voice |
| `PIPER_VOICE_MODEL` | `en_US-kathleen-high` | Voice model (clearer than GLaDOS) |
| `PIPER_LENGTH_SCALE` | `1.1` | Speech speed (higher = slower/clearer) |
| `PIPER_VOLUME_BOOST` | `1.0` | Volume multiplier for better recognition |

## Notes

- **One-way communication**: Linux → Windows only
- **Windows must be listening**: Voice Assistant should be active
- **Audio quality matters**: Clear audio improves recognition
- **Limited to Voice Assistant commands**: Can't use custom commands
- **Voice Clarity**: kathleen-high voice (with `USE_DIRECT_PIPER=true`) provides clearer speech than GLaDOS for Windows Voice Assistant
- **Speech Speed**: `PIPER_LENGTH_SCALE=1.1` slows speech by 10% for better recognition
- **Volume Adjustment**: `PIPER_VOLUME_BOOST` requires sox or ffmpeg to be installed

For more advanced control (precise clicks, complex automation), use the Computer Control Agent directly on Windows instead. See [COMPUTER_CONTROL_AGENT.md](COMPUTER_CONTROL_AGENT.md).

## See Also

- [WINDOWS_VOICE_ASSIST_SETUP.md](WINDOWS_VOICE_ASSIST_SETUP.md) - Complete setup guide
- [COMPUTER_CONTROL_AGENT.md](COMPUTER_CONTROL_AGENT.md) - Vision-based automation
- [PI_SETUP.md](PI_SETUP.md) - Raspberry Pi client setup
