# Qwen-Agent Directory

This directory contains the Qwen-based AI agent implementations for HAssistant.

## Contents

- **`pc_control_agent.py`** - Voice-controlled PC assistant (main implementation)
- **`Dockerfile`** - Container configuration for the agent
- **`requirements.txt`** - Python dependencies
- **`start_agent.sh`** - Quick start script
- **`test_pc_control.py`** - Test suite for the agent
- **`PC_CONTROL_AGENT.md`** - Complete documentation
- **`EXAMPLES.md`** - Usage examples and command reference
- **`integration_example.py`** - Home Assistant integration examples

## Quick Start

### Using Docker (Recommended)

```bash
# Build and start the agent
cd /home/runner/work/HAssistant/HAssistant
docker-compose up -d qwen-agent

# Run interactively
docker exec -it hassistant-qwen-agent python3 /app/pc_control_agent.py
```

### Standalone

```bash
# Install dependencies
pip install -r requirements.txt

# Run the agent
./start_agent.sh
```

## Features

The Qwen PC Control Agent provides:

- 🎤 **Voice Input**: Whisper STT integration
- 🧠 **Natural Language**: Qwen LLM for command interpretation
- 🖥️ **PC Control**: Application, volume, file, and system control
- 🔒 **Safe Execution**: Predefined commands only
- 🌐 **Cross-Platform**: Linux, macOS, Windows support

## Documentation

- [PC_CONTROL_AGENT.md](PC_CONTROL_AGENT.md) - Full documentation
- [EXAMPLES.md](EXAMPLES.md) - Command examples and use cases
- [integration_example.py](integration_example.py) - Integration code

## Requirements

- Python 3.11+
- Whisper STT service (http://hassistant-whisper:10300)
- Ollama with Qwen model (http://ollama-chat:11434)
- Microphone for voice input
- Audio libraries (PyAudio, ALSA)

## Architecture

```
Voice → Microphone → PyAudio → WAV file
                                   ↓
                              Whisper STT
                                   ↓
                              Text transcription
                                   ↓
                              Qwen LLM (via Ollama)
                                   ↓
                              Structured command (JSON)
                                   ↓
                              Command executor
                                   ↓
                              System action (open app, etc.)
```

## Supported Commands

- **Applications**: open, close
- **Volume**: up, down, mute, unmute
- **Screen**: lock, screenshot
- **Files**: open, list
- **System**: get info, stats

See [EXAMPLES.md](EXAMPLES.md) for complete command reference.

## Testing

```bash
# Basic structure test (no dependencies required)
python3 test_pc_control.py

# Full test (requires all dependencies)
pip install -r requirements.txt
python3 test_pc_control.py --full
```

## Configuration

Environment variables:

```bash
export WHISPER_STT_URL=http://hassistant-whisper:10300
export OLLAMA_URL=http://ollama-chat:11434
export QWEN_MODEL=qwen2.5:7b
```

## Extending

To add new commands:

1. Edit `pc_control_agent.py`
2. Add command to `self.commands` dictionary
3. Implement the command method
4. Update Qwen prompt to include new action
5. Test and document

## Troubleshooting

### Audio Issues
```bash
# Test microphone
arecord -d 3 test.wav && aplay test.wav

# Check PyAudio devices
python3 -c "import pyaudio; pa = pyaudio.PyAudio(); print(f'Devices: {pa.get_device_count()}')"
```

### STT Connection
```bash
# Test Whisper STT
curl http://localhost:10300
```

### LLM Connection
```bash
# Test Ollama
curl http://localhost:11434/api/tags

# Test Qwen model
curl http://localhost:11434/api/generate \
  -d '{"model": "qwen2.5:7b", "prompt": "Hello", "stream": false}'
```

## Integration

### With Home Assistant

See [integration_example.py](integration_example.py) for examples.

### With Other Services

The agent can be extended to work with:
- Home Assistant automations
- Node-RED flows
- Custom REST APIs
- Python scripts

## Contributing

Contributions welcome! To add features:

1. Fork the repository
2. Create your feature branch
3. Add tests
4. Update documentation
5. Submit a pull request

## License

Part of HAssistant - MIT License

## See Also

- [Main README](../README.md) - Project overview
- [pi_client.py](../pi_client.py) - Raspberry Pi voice client
- [HA_ASSIST_SETUP.md](../HA_ASSIST_SETUP.md) - Home Assistant setup
