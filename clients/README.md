# Client Scripts

This directory contains client scripts that connect to and interact with the HAssistant services.

## Available Clients

### pi_client.py
**Purpose**: Raspberry Pi voice client for wake word detection and voice processing

**Features**:
- Porcupine wake word detection
- Integrates with Home Assistant Assist API
- Audio capture and playback
- Automatic reconnection
- Status indicators

**Setup**: See [docs/setup/PI_SETUP.md](../docs/setup/PI_SETUP.md)

**Usage**:
```bash
# Copy configuration
cp config/pi_client.env.example pi_client.env
# Edit configuration
nano pi_client.env
# Run client
python3 pi_client.py
```

---

### pi_client_usb_audio.py
**Purpose**: Variant of Pi client with USB audio support

**Features**: Same as pi_client.py but optimized for USB audio devices

---

### windows_voice_control.py
**Purpose**: Control Windows laptop using Windows Voice Assistant via audio cable

**Features**:
- Sends TTS commands to Windows Voice Assistant
- Routes audio through USB dongle to Windows headset port
- Sanitizes and validates commands
- Supports voice control of Windows applications

**Setup**: See [docs/setup/WINDOWS_VOICE_ASSIST_SETUP.md](../docs/setup/WINDOWS_VOICE_ASSIST_SETUP.md)

**Usage**:
```bash
# Copy configuration
cp config/windows_voice_control.env.example .env
# Run command
python3 windows_voice_control.py "Open Notepad"
```

---

### computer_control_agent.py
**Purpose**: Vision-based computer control agent for GUI automation

**Features**:
- Uses vision-gateway for screenshots
- PyAutoGUI for mouse/keyboard control
- OCR with Tesseract
- Excel, browser, and application automation
- Optional Windows Voice mode

**Setup**: See [docs/architecture/COMPUTER_CONTROL_AGENT.md](../docs/architecture/COMPUTER_CONTROL_AGENT.md)

**Usage**:
```bash
# Install dependencies
pip install -r config/computer_control_requirements.txt
# Copy configuration
cp config/computer_control_agent.env.example computer_control_agent.env
# Run task
python3 computer_control_agent.py --task "Open notepad"
```

---

### ha_integration.py
**Purpose**: Flask webhook server for Home Assistant integration

**Features**:
- Webhook endpoint for HA automations
- Integrates computer control agent
- Supports both direct and Windows Voice modes

**Usage**:
```bash
python3 ha_integration.py
```

Then configure Home Assistant automation to POST to:
```
http://<server-ip>:5001/webhook
```

---

## Docker Support

### Dockerfile.computer_control
Docker image for running the computer control agent in a container.

**Build**:
```bash
docker build -f clients/Dockerfile.computer_control -t hassistant-computer-control .
```

**Run**:
See commented section in `docker-compose.yml` for full configuration.
