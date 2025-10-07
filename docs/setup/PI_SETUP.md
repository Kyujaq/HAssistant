# Raspberry Pi Client Setup for GLaDOS Voice Interaction

This guide will get your Raspberry Pi talking to GLaDOS using Home Assistant's Assist API.

## Architecture

```
Raspberry Pi → Porcupine Wake Word → HA Whisper STT → Ollama (Hermes3) → Piper TTS (GLaDOS voice) → Pi Speaker
```

## Prerequisites

1. **Raspberry Pi** (3B+ or newer recommended)
2. **USB Microphone** or Pi HAT with mic
3. **Speaker** (USB, 3.5mm, or HAT)
4. **Network access** to your Home Assistant server

## Installation

### 1. Install System Dependencies

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv portaudio19-dev alsa-utils

# Test your audio devices
aplay -l  # List playback devices
arecord -l  # List recording devices
```

### 2. Create Python Environment

```bash
cd ~
python3 -m venv glados-env
source glados-env/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install --upgrade pip
pip install pvporcupine numpy sounddevice requests pyaudio
```

### 4. Get Picovoice Access Key

1. Go to https://console.picovoice.ai/
2. Sign up for free account
3. Create a new access key
4. Copy the key

### 5. Configure Pi Client

```bash
# Copy the client script and config
scp user@glad0s:/home/qjaq/HAssistant/pi_client.py ~/
scp user@glad0s:/home/qjaq/HAssistant/pi_client.env.example ~/.env

# Edit configuration
nano ~/.env

# Optional: align with shared automation services
echo "WINDOWS_VOICE_CONTROL_URL=http://windows-voice-control:8085" >> ~/.env
```

Set your:
- `PV_ACCESS_KEY` (from Picovoice)
- `HA_URL` (your Home Assistant URL)
- `HA_TOKEN` (from HA: Profile → Long-Lived Access Tokens)

### 6. Test Audio

```bash
# Test microphone
arecord -d 5 -f cd test.wav
aplay test.wav

# Test speaker
speaker-test -t wav -c 2
```

### 7. Run the Client

```bash
# Load environment variables
export $(cat ~/.env | xargs)

# Run the client
python3 ~/pi_client.py
```

You should see:
```
🚀 GLaDOS Pi Client Starting...
👂 Listening for wake word: 'computer'...
```

### 8. Test Voice Interaction

Say: **"Computer"** (or your chosen wake word)
- You should hear an acknowledgment beep
- Speak your command: "Turn on the living room lights"
- GLaDOS will respond with her characteristic voice

## Auto-Start on Boot

Create a systemd service:

```bash
sudo nano /etc/systemd/system/glados-client.service
```

```ini
[Unit]
Description=GLaDOS Voice Client
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
EnvironmentFile=/home/pi/.env
ExecStart=/home/pi/glados-env/bin/python3 /home/pi/pi_client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable glados-client
sudo systemctl start glados-client

# Check status
sudo systemctl status glados-client

# View logs
journalctl -u glados-client -f
```

## Troubleshooting

### No Audio Output

```bash
# Check ALSA config
aplay -L

# Set default device in ~/.asoundrc
pcm.!default {
    type hw
    card 0
}
```

### Microphone Not Working

```bash
# Test microphone levels
alsamixer  # Use F4 to see capture devices, adjust levels

# Record test
arecord -d 5 -f S16_LE -r 16000 test.wav
```

### Wake Word Not Detected

- Ensure `PV_ACCESS_KEY` is correct
- Try different wake words (`jarvis`, `computer`, `hey google`)
- Check microphone volume with `alsamixer`
- Reduce background noise

### Connection Errors

- Verify `HA_URL` is correct (use IP if hostname fails)
- Check HA token is valid
- Ensure Pi can reach HA: `ping glad0s` or `ping <HA_IP>`

## Custom Wake Word

To train a custom "GLaDOS" wake word:

1. Go to https://console.picovoice.ai/
2. Go to "Porcupine Wake Word"
3. Train custom wake word "GLaDOS"
4. Download the `.ppn` file for Raspberry Pi
5. Update `.env`:
   ```
   WAKE_WORD_MODEL=/home/pi/glados_en_raspberry-pi_v3_0_0.ppn
   ```

## Performance Tips

- Use Pi 4 (2GB+ RAM) for best performance
- Close unnecessary services
- Use wired Ethernet for stability
- Keep Pi cool (passive heatsink recommended)

## Next Steps

- Configure HA automations (see `/examples/automations.yaml`)
- Add calendar integration for context-aware responses
- Create custom scenes triggered by voice
- Train custom wake word for "GLaDOS"
