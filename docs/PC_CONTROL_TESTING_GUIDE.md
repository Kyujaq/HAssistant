# PC Control Agent Testing Guide (Windows Voice Mode)

## Overview
The PC Control Agent uses **Text-to-Speech (TTS) → Windows Voice Assistant** to control a Windows PC remotely without installing any software on the Windows machine.

## Architecture Flow

```
┌─────────────────────┐
│ Computer Control    │  Decides what command to execute
│     Agent           │
└──────────┬──────────┘
           │
    ┌──────▼───────────┐
    │ windows_voice_   │  Formats voice commands
    │ control.py       │
    └──────┬───────────┘
           │
    ┌──────▼───────────┐
    │ Piper TTS        │  Synthesizes speech
    │ (hassistant-     │  (en_US-kathleen-high voice)
    │  piper-glados)   │
    └──────┬───────────┘
           │
    ┌──────▼───────────┐
    │ USB Audio Device │  hw:1,0 (USB dongle)
    │ (aplay output)   │
    └──────┬───────────┘
           │
    [3.5mm aux cable]
           │
    ┌──────▼───────────┐
    │ Windows PC       │  Listens via microphone
    │ Voice Assistant  │  Executes commands
    └──────────────────┘
```

## Prerequisites

### Hardware Setup
1. **USB Audio Dongle** - Connected to Linux machine
   - Should appear as `hw:1,0` (check with `aplay -l`)
   - Configured in `.env` as `USB_AUDIO_DEVICE=hw:1,0`

2. **3.5mm Aux Cable** - Connects USB dongle output → Windows PC microphone input
   - USB dongle headphone jack → Windows laptop mic jack

3. **Windows PC** - Target machine
   - Windows Voice Assistant enabled
   - Microphone set to 3.5mm aux input
   - Voice Assistant listening and responsive

### Software Setup (Linux/HAssistant Side)
1. **Services Running**:
   ```bash
   docker compose ps | grep piper
   # Should show: hassistant-piper-glados running on port 10200
   ```

2. **Environment Variables** (in `.env`):
   ```bash
   # TTS Configuration
   USE_DIRECT_PIPER=true
   PIPER_EXECUTABLE=/usr/bin/piper
   PIPER_VOICE_MODEL=en_US-kathleen-high  # Clearer than GLaDOS for voice recognition
   PIPER_LENGTH_SCALE=1.1  # Slower speech for clarity (10% slower)
   PIPER_VOLUME_BOOST=1.0  # Adjust if Windows can't hear

   # USB Audio Device
   USB_AUDIO_DEVICE=hw:1,0
   USE_PULSEAUDIO=false

   # Computer Control Agent Mode
   USE_WINDOWS_VOICE=true  # CRITICAL: Enables Windows Voice mode
   ```

3. **Python Dependencies**:
   ```bash
   cd /home/qjaq/HAssistant/clients
   # Only need basic deps for TTS mode (no PyAutoGUI needed!)
   python3 -c "import requests, subprocess; print('✓ OK')"
   ```

## Testing Steps

### Step 1: Test Audio Output
Test that TTS audio reaches the USB dongle:

```bash
cd /home/qjaq/HAssistant/clients
python3 windows_voice_control.py --test
```

**Expected Output**:
```
Testing audio device: hw:1,0
Audio system status:
[list of audio cards]
```

**Troubleshooting**:
- If no audio devices found: Check `aplay -l` to find correct device ID
- Update `USB_AUDIO_DEVICE` in `.env` if needed

### Step 2: Test TTS Generation
Test that Piper TTS generates clear speech:

```bash
python3 windows_voice_control.py "Hello Windows"
```

**Expected Output**:
```
[INFO] Synthesizing: Hello Windows
✅ TTS audio saved to /tmp/windows_tts_XXXXX.wav
[INFO] Playing via ALSA: hw:1,0
✅ Command sent successfully
```

**What to Verify**:
- Audio should play through USB dongle (you can test with headphones)
- Voice should be clear and slow enough for recognition
- No audio glitches or distortion

**Troubleshooting**:
- If too quiet: Increase `PIPER_VOLUME_BOOST` in `.env` (try 1.5 or 2.0)
- If too fast: Increase `PIPER_LENGTH_SCALE` (try 1.2 or 1.3)
- If garbled: Check cable connection and Windows mic input level

### Step 3: Test Windows Voice Assistant (Manual)
Before automating, verify Windows can hear and respond:

1. **On Windows PC**:
   - Enable Windows Voice Assistant (Windows key + H or Settings → Accessibility → Voice Access)
   - Set microphone input to 3.5mm aux cable
   - Test microphone level (Settings → Sound → Input device)

2. **From Linux**:
   ```bash
   python3 windows_voice_control.py "Open Notepad"
   ```

3. **On Windows**: Watch for Voice Assistant to:
   - Show "Listening..." indicator
   - Display recognized text: "Open Notepad"
   - Execute command (Notepad opens)

**Common Issues**:
- **Windows doesn't respond**: Check mic input source and volume level
- **Wrong command recognized**: Speech too fast (increase `PIPER_LENGTH_SCALE`)
- **No response**: Cable disconnected or Windows Voice Assistant not listening

### Step 4: Test Individual Commands
Test each command type:

```bash
# Open application
python3 windows_voice_control.py "Open Calculator"

# Type text
python3 windows_voice_control.py "Type Hello World"

# Send keystroke
python3 windows_voice_control.py "Press Enter"

# Or use convenience flags:
python3 windows_voice_control.py --open "Notepad"
python3 windows_voice_control.py --type "Hello from Linux"
python3 windows_voice_control.py --key Enter
```

### Step 5: Test Computer Control Agent Integration
Test the full agent with Windows Voice mode:

```bash
cd /home/qjaq/HAssistant/clients

# Set environment for Windows Voice mode
export USE_WINDOWS_VOICE=true
export VISION_GATEWAY_URL=http://localhost:8088
export OLLAMA_URL=http://localhost:11434

# Run agent (interactive mode)
python3 computer_control_agent.py
```

**What It Does**:
1. Agent imports `windows_voice_control` module
2. Uses `speak_command()`, `type_text()`, etc. instead of PyAutoGUI
3. All commands route through TTS → Windows Voice Assistant

**Simple Test Task**:
```python
from computer_control_agent import ComputerControlAgent

agent = ComputerControlAgent(use_windows_voice=True)

# Test opening application
action = {
    "type": "open_app",
    "params": {"app_name": "Calculator"},
    "description": "Open Calculator via voice"
}

success = agent.execute_action(action)
print(f"Result: {'✓ Success' if success else '✗ Failed'}")
```

## Verification Checklist

Before testing tomorrow:

- [ ] USB audio dongle connected and recognized (`aplay -l` shows hw:1,0)
- [ ] 3.5mm cable connects dongle → Windows mic jack
- [ ] Windows Voice Assistant enabled and listening
- [ ] Windows mic input set to 3.5mm aux (not internal mic!)
- [ ] `USE_WINDOWS_VOICE=true` in `.env` or export
- [ ] Piper TTS service running (`docker compose ps | grep piper`)
- [ ] Test audio output: `python3 windows_voice_control.py --test`
- [ ] Test simple command: `python3 windows_voice_control.py "Open Notepad"`
- [ ] Verify Windows responds to voice command

## Configuration Tuning

### If Windows Can't Hear Commands:
1. Increase volume: `PIPER_VOLUME_BOOST=1.5` (or 2.0)
2. Check Windows mic input level (should show activity when TTS plays)
3. Test cable with headphones (should hear clear speech)

### If Commands Are Misunderstood:
1. Slow down speech: `PIPER_LENGTH_SCALE=1.2` (or 1.3)
2. Try different voice: `PIPER_VOICE_MODEL=en_US-amy-medium`
3. Simplify commands (shorter phrases)

### If Too Much Latency:
1. Reduce audio buffer if possible
2. Use shorter commands
3. Accept 1-2 second delay (TTS generation + speech + Windows processing)

## Known Limitations

1. **One Command At a Time**: Each command needs ~2-3 seconds for TTS + playback + Windows processing
2. **Background Noise**: Windows Voice Assistant may trigger on ambient noise
3. **Command Format**: Must match Windows Voice Assistant syntax exactly
4. **No Visual Feedback**: Can't see if Windows recognized command without Vision Gateway

## Crew Orchestrator Integration (Multi-Agent System)

Once basic testing works, you can enable the **Crew Orchestrator** for intelligent multi-step automation:

### What is Crew Orchestrator?

A three-agent system that automates complex UI tasks:
1. **Planner Agent**: Breaks down goals into step-by-step plans
2. **Action Agent**: Executes voice commands via Windows Voice Control
3. **Verifier Agent**: Checks if actions succeeded using Vision Gateway

### Enabling Crew Orchestrator

1. **Uncomment in docker-compose.yml**:
   ```bash
   # Find the crew-orchestrator section and uncomment it
   nano docker-compose.yml
   ```

2. **Build and start**:
   ```bash
   docker compose build crew-orchestrator
   docker compose up -d crew-orchestrator
   ```

3. **Verify it's running**:
   ```bash
   curl http://localhost:8084/healthz
   ```

### Using Crew Orchestrator

**Simple Test** (Excel):
```bash
curl -X POST http://localhost:8084/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Create a new Excel spreadsheet with columns Name, Age, Email",
    "application": "Excel"
  }'
```

**Generic Application** (Chrome):
```bash
curl -X POST http://localhost:8084/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Open Chrome and navigate to github.com",
    "application": "Chrome"
  }'
```

**Notepad Test**:
```bash
curl -X POST http://localhost:8084/crew/task/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Open Notepad and type Hello World",
    "application": "Notepad"
  }'
```

### How It Works

1. **You send a goal** → `"Create Excel spreadsheet with headers"`
2. **Planner breaks it down** →
   - Step 1: "Open Excel" + verify "Is Excel open?"
   - Step 2: "Click cell A1" + verify "Is A1 selected?"
   - Step 3: "Type Name" + verify "Does A1 contain Name?"
   - etc.
3. **Action Agent executes** → Sends voice commands one by one
4. **Verifier checks** → Uses Vision Gateway cache to confirm success
5. **Self-corrects** → If verification fails, can retry or adjust

### Benefits

- ✅ **Autonomous**: No need to manually script each step
- ✅ **Self-verifying**: Checks work using vision
- ✅ **Adaptive**: Can adjust if things don't work as expected
- ✅ **Extensible**: Add new applications easily (just specify in goal)

### Limitations & Next Steps

**Current Status** (as of today):
- ✅ Planner creates step-by-step plans
- ✅ Voice tool integration complete
- ✅ Vision verification with cache support
- ⚠️ Full execution loop needs testing (plan → execute → verify → adjust)

**Next Phase** (after tomorrow's testing):
1. Test full execution loop with real Windows PC
2. Add error recovery (retry failed steps)
3. Add task history/logging
4. Create Home Assistant integration for voice commands

## Example Usage Scenarios

### Scenario 1: Fill Out Excel Spreadsheet
```python
agent = ComputerControlAgent(use_windows_voice=True)

# Open Excel
agent.windows_voice_bridge['open_application']("Excel")
time.sleep(2)

# Navigate and enter data
agent.windows_voice_bridge['speak_command']("Create new workbook")
time.sleep(2)

agent.windows_voice_bridge['type_text']("Name")
agent.windows_voice_bridge['send_keystroke']("Tab")

agent.windows_voice_bridge['type_text']("Age")
agent.windows_voice_bridge['send_keystroke']("Tab")

agent.windows_voice_bridge['type_text']("Email")
agent.windows_voice_bridge['send_keystroke']("Enter")
```

### Scenario 2: Web Research
```python
# Open browser
agent.windows_voice_bridge['open_application']("Chrome")
time.sleep(2)

# Navigate
agent.windows_voice_bridge['speak_command']("Go to github.com")
time.sleep(2)

# Search
agent.windows_voice_bridge['type_text']("anthropic claude")
agent.windows_voice_bridge['send_keystroke']("Enter")
```

## Troubleshooting Guide

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| No audio from USB dongle | Wrong device ID | Check `aplay -l`, update `USB_AUDIO_DEVICE` |
| Windows doesn't respond | Mic input not set to aux | Check Windows Sound settings |
| Commands recognized wrong | Speech too fast | Increase `PIPER_LENGTH_SCALE` |
| Audio too quiet | Volume too low | Increase `PIPER_VOLUME_BOOST` |
| TTS fails | Piper not running | `docker compose up -d piper-glados` |
| Import error | Module not found | Check `sys.path`, run from `clients/` directory |
| Cable issues | Bad connection | Try different cable, check connections |

## Success Criteria

You'll know it's working when:

1. ✅ USB audio dongle plays TTS audio
2. ✅ Windows shows "Listening..." when TTS plays
3. ✅ Windows displays recognized command text
4. ✅ Windows executes command (Notepad opens, text types, etc.)
5. ✅ Python script reports `✅ Command sent successfully`

Tomorrow's goal: **Get at least one command working end-to-end** (e.g., "Open Notepad")
