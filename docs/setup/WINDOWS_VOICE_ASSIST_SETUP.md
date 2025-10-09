# Windows Voice Assistant Control via Audio Cable

This guide explains how to control a Windows laptop using Windows Voice Assistant (Cortana/Voice Access) by routing audio from a Linux server's Piper TTS through a 3.5mm aux cable.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Linux Server (HAssistant)                   │
│                                                                 │
│  ┌──────────────┐     ┌─────────────────┐                     │
│  │   Piper TTS  │ ──► │ USB Audio Dongle│ ─────┐              │
│  │  (kathleen)  │     │   (3.5mm out)   │      │              │
│  └──────────────┘     └─────────────────┘      │              │
│                                                 │              │
└─────────────────────────────────────────────────┼──────────────┘
                                                  │
                                    3.5mm Aux Cable
                                                  │
┌─────────────────────────────────────────────────┼──────────────┐
│                    Windows Laptop                │              │
│                                                  │              │
│  ┌─────────────────────────────────────────┐    │              │
│  │        Headset/Microphone Port          │ ◄──┘              │
│  └────────────────┬────────────────────────┘                   │
│                   │                                             │
│                   ▼                                             │
│  ┌─────────────────────────────────────────┐                   │
│  │      Windows Voice Assistant            │                   │
│  │   (Cortana / Voice Access / WSR)        │                   │
│  │                                          │                   │
│  │  • Listens to audio from headset port   │                   │
│  │  • Executes voice commands               │                   │
│  │  • Controls applications                 │                   │
│  └─────────────────────────────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Note:** The default setup uses GLaDOS voice, but for better Windows Voice Assistant recognition, it's recommended to use the clearer kathleen-high voice (see Section 5.2).

## Prerequisites

### Linux Server Side
1. HAssistant services running (Piper TTS)
2. USB audio dongle with 3.5mm output jack
3. 3.5mm aux cable (male-to-male)
4. ALSA or PulseAudio installed
5. *Optional:* sox or ffmpeg (for volume boost feature)
6. *Optional:* Piper with kathleen-high voice model (for clearer speech)

### Windows Laptop Side
1. Windows 10/11 with Voice Assistant enabled
2. 3.5mm headset/microphone port
3. Windows Voice Access or Cortana configured

---

## Part 1: Linux Server Audio Configuration

### 1.1 Install Required Packages

```bash
# Install ALSA utilities and PulseAudio
sudo apt-get update
sudo apt-get install alsa-utils pulseaudio pulseaudio-utils
```

### 1.2 Identify USB Audio Dongle

```bash
# List all audio devices
aplay -L

# Or with more detail
aplay -l

# Expected output should include your USB audio device, e.g.:
# card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
```

Note the card number and device number (e.g., `hw:1,0`).

### 1.3 Test Audio Output to USB Dongle

```bash
# Test with a simple tone
speaker-test -D hw:1,0 -c 2 -t wav

# Test with existing audio file
aplay -D hw:1,0 /usr/share/sounds/alsa/Front_Center.wav
```

If you hear sound from the USB dongle, the hardware is working!

### 1.4 Configure ALSA Default Device

Create or edit `~/.asoundrc`:

```bash
nano ~/.asoundrc
```

Add the following configuration (adjust card/device numbers):

```
# Set USB audio dongle as default output
pcm.!default {
    type hw
    card 1
    device 0
}

ctl.!default {
    type hw
    card 1
}

# Alternative: Use PulseAudio routing
# pcm.!default {
#     type pulse
# }
# ctl.!default {
#     type pulse
# }
```

### 1.5 Configure PulseAudio (Alternative Method)

If using PulseAudio (recommended for easier management):

```bash
# List PulseAudio sinks (output devices)
pactl list sinks short

# Set USB audio as default sink
pactl set-default-sink alsa_output.usb-YOUR_USB_DEVICE_NAME

# Or use pavucontrol for GUI configuration
sudo apt-get install pavucontrol
pavucontrol
```

In `pavucontrol`:
1. Go to **Configuration** tab
2. Select your USB audio device
3. Set profile to "Analog Stereo Output"
4. Go to **Output Devices** tab
5. Set your USB device as fallback

---

## Part 2: Configure Piper TTS Output

### 2.1 Modify pi_client.py for USB Audio Output

Edit the `speak` method in `pi_client.py` to use the USB audio device:

```python
def speak(self, text: str):
    """Convert text to GLaDOS voice and play through USB dongle"""
    logger.info("🔊 Speaking with GLaDOS voice to USB audio...")

    try:
        # Call Piper TTS service
        url = f"{TTS_URL}/synthesize"
        params = {"text": text}

        response = requests.get(url, params=params, stream=True, timeout=10)

        if response.status_code != 200:
            logger.error(f"TTS failed: {response.status_code}")
            return

        # Save audio temporarily
        temp_audio = f"/tmp/glados_tts_{int(time.time())}.wav"
        with open(temp_audio, 'wb') as f:
            for chunk in response.iter_content(chunk_size=4096):
                f.write(chunk)

        # Play audio through USB dongle (specify device explicitly)
        # Option 1: Using ALSA directly
        subprocess.run(['aplay', '-D', 'hw:1,0', '-q', temp_audio], check=False)
        
        # Option 2: Using PulseAudio (if configured)
        # subprocess.run(['paplay', '--device=alsa_output.usb-YOUR_DEVICE', temp_audio], check=False)
        
        os.remove(temp_audio)

    except Exception as e:
        logger.error(f"Error in TTS: {e}")
```

### 2.2 Add Volume Control

Adjust volume for optimal Windows Voice Assistant recognition:

```bash
# Set volume to 100% for USB device (adjust card number)
amixer -c 1 set PCM 100%

# Or using PulseAudio
pactl set-sink-volume alsa_output.usb-YOUR_DEVICE 100%
```

### 2.3 Test TTS Output

```bash
# Test Piper TTS directly to USB dongle
echo "Hello, this is a test" | \
docker exec -i hassistant-piper-glados /usr/share/piper/piper \
  --model /data/en_US-glados-high.onnx \
  --output_file - | \
aplay -D hw:1,0 -q -
```

---

## Part 3: Windows Laptop Configuration

### 3.1 Enable Windows Voice Assistant

**For Windows 11:**

1. Open **Settings** → **Accessibility** → **Voice Access**
2. Toggle **Voice Access** to **On**
3. Complete the voice training tutorial
4. Ensure microphone is set to your headset port

**For Windows 10 (Cortana):**

1. Open **Settings** → **Cortana**
2. Enable **"Hey Cortana"**
3. Set microphone to headset port

**For Windows Speech Recognition:**

1. Open **Control Panel** → **Speech Recognition**
2. Click **Start Speech Recognition**
3. Follow setup wizard
4. Select headset microphone as input

### 3.2 Configure Audio Input Device

1. Right-click **speaker icon** in taskbar → **Sounds**
2. Go to **Recording** tab
3. Select your **headset microphone** (the port where aux cable is connected)
4. Click **Set Default**
5. Click **Properties** → **Levels**
6. Set **Microphone Boost** to +20dB or +30dB for better recognition
7. Go to **Listen** tab
8. Optionally enable **"Listen to this device"** for testing

### 3.3 Test Voice Recognition

1. Connect the 3.5mm cable from Linux server USB dongle to Windows headset port
2. On Linux server, trigger TTS:
   ```bash
   python3 pi_client.py
   # Or test with:
   echo "Open Notepad" | docker exec -i hassistant-piper-glados /usr/share/piper/piper \
     --model /data/en_US-glados-high.onnx --output_file - | aplay -D hw:1,0 -q -
   ```
3. Windows should recognize the audio and execute commands

---

## Part 4: Voice Commands for Computer Control

### 4.1 Common Windows Voice Commands

Once Windows Voice Assistant is listening to the audio cable input:

**Application Control:**
- "Open Notepad"
- "Open Microsoft Edge"
- "Open File Explorer"
- "Close window"

**Typing & Editing:**
- "Type [your text]"
- "Press Enter"
- "Select all"
- "Copy that"
- "Paste"

**System Control:**
- "Show desktop"
- "Minimize window"
- "Maximize window"
- "Switch to [app name]"

**Windows 11 Voice Access Specific:**
- "Click [button name]"
- "Press [key name]"
- "Show numbers" (displays clickable numbers on screen)
- "Click [number]"

### 4.2 Integration with HAssistant

Create a custom script to send commands via Piper TTS:

```python
#!/usr/bin/env python3
"""
Windows Voice Control Bridge
Sends commands to Windows laptop via audio cable
"""

import requests
import subprocess
import time
import os

TTS_URL = "http://localhost:10200"  # Adjust if needed
USB_AUDIO_DEVICE = "hw:1,0"  # Your USB dongle

def speak_command(command: str):
    """Send voice command to Windows via Piper TTS + audio cable"""
    print(f"Sending command: {command}")
    
    # Get TTS audio from Piper
    response = requests.get(f"{TTS_URL}/synthesize", params={"text": command}, stream=True)
    
    if response.status_code != 200:
        print(f"TTS failed: {response.status_code}")
        return False
    
    # Save temporarily
    temp_file = f"/tmp/win_cmd_{int(time.time())}.wav"
    with open(temp_file, 'wb') as f:
        for chunk in response.iter_content(chunk_size=4096):
            f.write(chunk)
    
    # Play through USB audio to Windows
    subprocess.run(['aplay', '-D', USB_AUDIO_DEVICE, '-q', temp_file], check=False)
    os.remove(temp_file)
    
    return True

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 windows_voice_control.py 'your command'")
        sys.exit(1)
    
    command = " ".join(sys.argv[1:])
    speak_command(command)
```

Save as `windows_voice_control.py` and use:

```bash
# Control Windows from Linux
python3 windows_voice_control.py "Open Notepad"
python3 windows_voice_control.py "Type Hello from Linux"
python3 windows_voice_control.py "Press Enter"
```

---

## Part 5: Advanced Configuration

### 5.1 Audio Quality Optimization

For better voice recognition:

1. **Increase sample rate** (if supported):
   ```bash
   # Check supported formats
   aplay -D hw:1,0 --dump-hw-params /usr/share/sounds/alsa/Front_Center.wav
   ```

2. **Adjust volume levels**:
   ```bash
   # Find optimal volume (usually 80-100%)
   amixer -c 1 set PCM 90%
   ```

3. **Reduce background noise**:
   - Use noise cancellation in PulseAudio
   - Or use `sox` for audio filtering

### 5.2 Voice Clarity Enhancement (Recommended)

For maximum clarity and reduced Windows Voice Assistant misunderstandings, use the kathleen-high voice model instead of GLaDOS:

**Edit your `.env` or `windows_voice_control.env.example`:**

```bash
# Enable direct Piper with clearer voice
USE_DIRECT_PIPER=true

# Use kathleen-high voice (clearer than GLaDOS for Windows)
PIPER_VOICE_MODEL=en_US-kathleen-high

# Slow down speech by 10% for better recognition
PIPER_LENGTH_SCALE=1.1

# Optional: Boost volume if Windows doesn't hear reliably
# Requires sox or ffmpeg installed
PIPER_VOLUME_BOOST=1.0  # Set to 1.2 or 1.5 if needed
```

**Why this helps:**
- kathleen-high has clearer pronunciation than GLaDOS
- `length_scale=1.1` slows speech by 10%, giving Windows more time to process
- Volume boost compensates for audio cable signal loss
- Direct Piper invocation bypasses HTTP overhead

**Install volume adjustment tools (optional):**
```bash
# For Debian/Ubuntu
sudo apt-get install sox

# Or use ffmpeg
sudo apt-get install ffmpeg
```

**Test the clearer voice:**
```bash
# Load new configuration
source .env

# Test command
python3 windows_voice_control.py "Hello Windows assistant, please open notepad"
```

### 5.3 Latency Reduction

Minimize delay between TTS and Windows recognition:

```bash
# Reduce ALSA buffer size
aplay -D hw:1,0 --buffer-size=1024 audio.wav

# Or configure in .asoundrc:
pcm.!default {
    type hw
    card 1
    device 0
    buffer_size 1024
}
```

### 5.4 Home Assistant Integration

Add to your Home Assistant `configuration.yaml`:

```yaml
shell_command:
  windows_voice_command: "python3 /path/to/windows_voice_control.py '{{ command }}'"

automation:
  - alias: "Control Windows via Voice"
    trigger:
      platform: conversation
      command:
        - "tell windows to [action]"
    action:
      - service: shell_command.windows_voice_command
        data:
          command: "{{ trigger.slots.action }}"
```

---

## Troubleshooting

### Issue: No sound from USB dongle

**Solution:**
```bash
# Check device is recognized
lsusb | grep -i audio

# Check ALSA sees the device
aplay -l

# Test directly
speaker-test -D hw:1,0 -c 2

# Check volume isn't muted
amixer -c 1 sget PCM
```

### Issue: Windows doesn't recognize voice

**Solution:**
1. Check Windows microphone input level (should show activity when audio plays)
2. Increase microphone boost in Windows sound settings
3. Re-train Windows Voice Access with actual TTS voice
4. Ensure cable is fully inserted into headset port (not line-in port)
5. **Use clearer voice (highly recommended):**
   ```bash
   # In .env file:
   USE_DIRECT_PIPER=true
   PIPER_VOICE_MODEL=en_US-kathleen-high
   PIPER_LENGTH_SCALE=1.1
   ```
   The kathleen-high voice is much clearer than GLaDOS for Windows Voice Assistant

### Issue: Audio too quiet or distorted

**Solution:**
```bash
# Adjust Linux output volume
amixer -c 1 set PCM 85%

# Use built-in volume boost (requires sox or ffmpeg)
# In .env file:
PIPER_VOLUME_BOOST=1.5  # 150% volume

# Or normalize audio with sox manually
sox input.wav output.wav norm -3

# Or use PulseAudio flat volumes
pactl set-sink-volume @DEFAULT_SINK@ 100%
```

### Issue: Intermittent recognition

**Solution:**
1. Check cable connection quality
2. Ensure USB dongle has stable power
3. Disable Windows mic enhancements (can cause issues):
   - Sound Settings → Recording → Microphone Properties → Enhancements → Disable all
4. **Use clearer voice model:**
   ```bash
   USE_DIRECT_PIPER=true
   PIPER_VOICE_MODEL=en_US-kathleen-high
   PIPER_LENGTH_SCALE=1.1  # Slower = more reliable recognition
   ```
5. Increase speech length scale for even slower/clearer speech:
   ```bash
   PIPER_LENGTH_SCALE=1.2  # 20% slower
   ```

### Issue: Computer Control Agent not working

The Computer Control Agent runs ON the Windows laptop itself (not via audio). For that use case:
- Install the Computer Control Agent on Windows
- Use vision-gateway for screenshot capture
- Use PyAutoGUI for mouse/keyboard control
- See [COMPUTER_CONTROL_AGENT.md](COMPUTER_CONTROL_AGENT.md)

---

## Testing Checklist

- [ ] USB audio dongle recognized by Linux
- [ ] Audio plays through USB dongle to 3.5mm output
- [ ] 3.5mm cable connected to Windows headset port
- [ ] Windows recognizes microphone input from headset port
- [ ] Windows Voice Assistant is enabled and listening
- [ ] Piper TTS output routes to USB audio device
- [ ] Windows recognizes spoken commands via audio cable
- [ ] Commands execute successfully on Windows

---

## Example Use Cases

### Use Case 1: Open Applications

```bash
# From Linux, make Windows open Notepad
python3 windows_voice_control.py "Open Notepad"
```

### Use Case 2: Type Text

```bash
# Type a message on Windows
python3 windows_voice_control.py "Type Hello World"
python3 windows_voice_control.py "Press Enter"
```

### Use Case 3: Control Excel

```bash
# Excel commands via Windows Voice Assistant
python3 windows_voice_control.py "Open Excel"
sleep 3
python3 windows_voice_control.py "Type Budget 2024"
python3 windows_voice_control.py "Press Tab"
python3 windows_voice_control.py "Type 1000"
```

### Use Case 4: Voice-Triggered Automation

Using Home Assistant:
1. Say "Hey GLaDOS, tell Windows to open Chrome"
2. HA triggers TTS command
3. Piper speaks "Open Chrome" via USB audio
4. Windows laptop hears it and opens Chrome

---

## Alternative: Direct Computer Control Agent

If you need more precise control (pixel-perfect clicks, complex automation), use the Computer Control Agent directly on Windows instead of audio commands:

1. **Install Python on Windows**
2. **Copy `computer_control_agent.py` to Windows**
3. **Install dependencies**: `pip install -r computer_control_requirements.txt`
4. **Run tasks**: `python computer_control_agent.py --task "your task"`

This gives you:
- Vision-based screen understanding
- Precise mouse/keyboard control
- Excel-specific features
- Complex task automation

See [COMPUTER_CONTROL_QUICK_START.md](COMPUTER_CONTROL_QUICK_START.md) for setup.

---

## Summary

This setup enables:
- ✅ Voice commands from Linux server to Windows laptop
- ✅ No additional Windows software required (uses built-in Voice Assistant)
- ✅ Simple hardware setup (USB audio dongle + aux cable)
- ✅ Integration with Home Assistant voice pipeline
- ✅ GLaDOS voice controlling Windows applications

**Limitations:**
- Only works with Windows Voice Assistant supported commands
- Requires Windows to be listening constantly
- Audio quality affects recognition accuracy
- One-way communication (Linux → Windows only)

For two-way interaction or more advanced control, consider:
- Installing Computer Control Agent on Windows
- Using Remote Desktop / VNC for full control
- Setting up network-based command interface
