# Qwen PC Control Agent

Voice-controlled PC assistant using Qwen LLM and Whisper STT.

## Features

- 🎤 **Voice Input**: Uses Whisper STT for accurate speech recognition
- 🧠 **Natural Language Understanding**: Qwen LLM interprets commands naturally
- 🖥️ **PC Control**: Execute system commands, control applications, manage files
- 🔒 **Safe Execution**: Structured command parsing with validation
- 🌐 **Cross-Platform**: Supports Linux, macOS, and Windows

## Architecture

```
Voice Input → Whisper STT → Qwen LLM → Command Parser → PC Control
                ↓               ↓            ↓              ↓
          Transcription    Understanding  Structure    Execution
```

## Supported Commands

### Application Control
- **Open applications**: "Open Firefox", "Launch terminal", "Start Chrome"
- **Close applications**: "Close Firefox", "Kill Chrome"

### System Control
- **Volume control**: "Increase volume", "Decrease volume", "Mute", "Unmute"
- **Screen control**: "Lock screen", "Take screenshot"

### File Management
- **Open files**: "Open document.pdf", "Open ~/Downloads/file.txt"
- **List files**: "List files in Downloads", "Show files in Documents"

### System Information
- **Get info**: "Show system info", "Check CPU usage", "How much memory is used?"

## Installation

### Prerequisites

1. **Whisper STT** running on your network (default: `http://hassistant-whisper:10300`)
2. **Ollama** with Qwen model (default: `http://ollama-chat:11434` with `qwen2.5:7b`)
3. **Audio input** (microphone)
4. **System dependencies** (auto-installed in Docker)

### Docker Deployment (Recommended)

The agent is included in the HAssistant docker-compose setup:

```bash
cd /home/runner/work/HAssistant/HAssistant
docker-compose up -d qwen-agent
```

To use interactively:
```bash
docker exec -it hassistant-qwen-agent python3 /app/pc_control_agent.py
```

### Standalone Installation

For running directly on your PC (not in container):

```bash
# Install dependencies
pip install -r requirements.txt

# On Linux, also install system packages
sudo apt-get install portaudio19-dev alsa-utils gnome-screenshot xdg-utils

# Set environment variables
export WHISPER_STT_URL=http://localhost:10300
export OLLAMA_URL=http://localhost:11434
export QWEN_MODEL=qwen2.5:7b

# Run the agent
python3 pc_control_agent.py
```

## Usage

### Interactive Mode

```bash
python3 pc_control_agent.py
```

Then:
1. Press **Enter** when ready to speak
2. Speak your command clearly
3. Wait for processing and execution
4. See the result

### Example Commands

```
User: "Open Firefox"
→ Opens Firefox browser

User: "Increase the volume"
→ Increases system volume by 5%

User: "Take a screenshot"
→ Saves screenshot to ~/Pictures/

User: "Show system info"
→ Displays CPU, memory, and disk usage

User: "List files in Downloads"
→ Shows files in Downloads directory

User: "Lock the screen"
→ Locks the screen
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_STT_URL` | `http://hassistant-whisper:10300` | Whisper STT service URL |
| `OLLAMA_URL` | `http://ollama-chat:11434` | Ollama API endpoint |
| `QWEN_MODEL` | `qwen2.5:7b` | Qwen model to use |
| `SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `SILENCE_THRESHOLD` | `0.02` | Silence detection threshold |
| `SILENCE_DURATION` | `2.0` | Silence duration to stop recording (seconds) |
| `MAX_RECORDING_DURATION` | `10` | Maximum recording duration (seconds) |

## Architecture Details

### Command Flow

1. **Audio Recording**: Captures voice input with silence detection
2. **STT Transcription**: Sends audio to Whisper for text conversion
3. **LLM Parsing**: Qwen interprets the text and extracts structured command
4. **Command Execution**: Safe execution of the parsed command
5. **Result Feedback**: Logs the result for user feedback

### Command Structure

Commands are parsed into structured format:

```python
{
    "action": "open_app",
    "target": "firefox",
    "parameters": {}
}
```

### Supported Actions

- `open_app`: Open an application
- `close_app`: Close an application
- `volume_up`: Increase volume
- `volume_down`: Decrease volume
- `mute`: Mute audio
- `unmute`: Unmute audio
- `lock_screen`: Lock the screen
- `screenshot`: Take a screenshot
- `open_file`: Open a file
- `list_files`: List files in directory
- `system_info`: Get system information

## Security Considerations

### Safe by Design

- **No arbitrary code execution**: Only predefined commands are allowed
- **Input validation**: All commands go through Qwen for validation
- **Limited scope**: Only common, safe operations are supported
- **No network access**: Commands are local to the PC only

### Extending Commands

To add new commands, edit `pc_control_agent.py`:

```python
# Add to self.commands dictionary in __init__
self.commands['my_command'] = self._my_command

# Implement the command
def _my_command(self, target: str, params: Dict) -> str:
    """My custom command"""
    # Your implementation
    return "Command executed"
```

## Troubleshooting

### Audio Recording Issues

```bash
# Test microphone
arecord -d 3 test.wav
aplay test.wav

# Check PyAudio
python3 -c "import pyaudio; print(pyaudio.PyAudio().get_device_count())"
```

### STT Connection Issues

```bash
# Test Whisper STT
curl -X POST http://localhost:10300/api/stt \
  -H "Content-Type: audio/wav" \
  --data-binary @test.wav
```

### Ollama Connection Issues

```bash
# Test Ollama
curl http://localhost:11434/api/tags

# Test Qwen model
curl http://localhost:11434/api/generate \
  -d '{"model": "qwen2.5:7b", "prompt": "Hello", "stream": false}'
```

### Command Not Working

Check logs for detailed error messages:
```bash
# Docker logs
docker logs hassistant-qwen-agent

# Or run with debug output
python3 pc_control_agent.py --debug
```

## Platform-Specific Notes

### Linux

- Uses `amixer` for volume control
- Uses `gnome-screenshot` for screenshots
- Uses `xdg-open` for opening files
- Requires X11 for GUI operations

### macOS

- Uses `osascript` for volume control
- Uses `screencapture` for screenshots
- Uses `open` for opening applications

### Windows

- Uses `start` for opening applications
- Uses `taskkill` for closing applications
- Limited volume control (requires additional implementation)

## Integration with HAssistant

The PC control agent integrates seamlessly with the HAssistant ecosystem:

- Uses existing **Whisper STT** service
- Connects to **Ollama** for Qwen LLM
- Can be triggered from **Home Assistant** automations
- Logs to standard output for monitoring

### Example Home Assistant Automation

```yaml
automation:
  - alias: "Voice PC Control"
    trigger:
      platform: conversation
      command: "control my pc to *"
    action:
      service: shell_command.qwen_pc_control
      data:
        command: "{{ trigger.command }}"
```

## Performance

- **Audio Recording**: Real-time with silence detection
- **STT Transcription**: ~1-2 seconds (depends on Whisper model)
- **LLM Parsing**: ~2-3 seconds (Qwen 2.5 7B on GPU)
- **Command Execution**: <1 second (depends on command)

**Total latency**: ~3-6 seconds from voice to execution

## Future Enhancements

- [ ] TTS feedback for command confirmation
- [ ] Wake word integration (like pi_client.py)
- [ ] Multi-turn conversations for complex commands
- [ ] Command history and undo
- [ ] GUI for command management
- [ ] Integration with Home Assistant sensors
- [ ] Support for macros and command chains
- [ ] Voice feedback using Piper TTS

## Contributing

To add new features or commands:

1. Fork the repository
2. Add your command implementation
3. Update the command list in `__init__`
4. Test on your platform
5. Submit a pull request

## License

Part of HAssistant project - MIT License

## See Also

- [HAssistant README](../README.md) - Main project documentation
- [pi_client.py](../pi_client.py) - Raspberry Pi voice client
- [HA_ASSIST_SETUP.md](../HA_ASSIST_SETUP.md) - Home Assistant setup
- [glados-orchestrator](../glados-orchestrator/) - Query routing service
