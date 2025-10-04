# HAssistant - Home Assistant + Ollama Voice Assistant

A complete voice assistant implementation using Home Assistant's native features, Ollama for local LLM processing, and Wyoming protocol for speech services. Features a GLaDOS-inspired personality with GPU-accelerated inference.

## Features

- **Local LLM Processing**: Ollama with GPU support (GTX 1080 Ti + GTX 1070)
- **Voice Interaction**: Wyoming Whisper (STT) + Piper (TTS) with GLaDOS voice
- **Raspberry Pi Client**: Wake word detection and voice processing
- **Home Assistant Integration**: Native Assist API integration
- **Memory System**: Letta Bridge with PostgreSQL + pgvector for contextual memory
- **Dual GPU Support**: Automatic GPU allocation for optimal performance
- **Multiple Models**: Switch between fast (Hermes-3 3B) and detailed (Qwen 2.5 7B) responses

## Architecture

```
┌─────────────────┐
│  Raspberry Pi   │  Wake word detection + audio I/O
│   (pi_client)   │
└────────┬────────┘
         │
┌────────▼────────┐
│ Home Assistant  │  Central hub + Assist API
└────────┬────────┘
         │
    ┌────┴────┬─────────┐
    │         │         │
┌───▼───┐ ┌──▼──────┐ ┌▼──────────┐
│Ollama │ │ Wyoming │ │Letta Bridge│  LLM + STT/TTS + Memory
│  LLM  │ │ Services│ │ + pgvector │
└───────┘ └─────────┘ └────────────┘
```

## Prerequisites

### Hardware
- NVIDIA GPU(s) with CUDA support
- Raspberry Pi (optional, for voice client)
- Microphone and speaker

### Software
- Docker & Docker Compose
- NVIDIA Container Toolkit
- Home Assistant instance (running on `assistant_default` network)
- Python 3.8+ (for Pi client)

## Quick Start

### 1. Clone and Configure

```bash
git clone <repo-url> HAssistant
cd HAssistant

# Copy and edit environment file
cp .env.example .env
# Edit .env with your Home Assistant URL and token
```

### 2. Start Services

```bash
# Start all services
docker compose up -d

# Verify services are running
docker compose ps
```

### 3. Load LLM Models

```bash
# Load Hermes-3 model (fast, sarcastic)
docker exec -it hassistant-ollama ollama create glados-hermes3 -f /root/.ollama/modelfiles/Modelfile.hermes3

# Load Qwen model (detailed, analytical)
docker exec -it hassistant-ollama ollama create glados-qwen -f /root/.ollama/modelfiles/Modelfile.qwen

# Verify models loaded
docker exec -it hassistant-ollama ollama list
```

### 4. Configure Home Assistant

1. Navigate to **Settings → Devices & Services**
2. Click **Add Integration** → Search for "Ollama"
3. Configure:
   - URL: `http://hassistant-ollama:11434`
   - Model: `glados-hermes3` or `glados-qwen`
4. Add Wyoming services:
   - **Whisper STT**: `tcp://hassistant-whisper:10300`
   - **Piper TTS**: `tcp://hassistant-piper:10200`

See [HA_ASSIST_SETUP.md](HA_ASSIST_SETUP.md) and [HA_VOICE_CONFIG.md](HA_VOICE_CONFIG.md) for detailed configuration.

## Configuration

### Environment Variables

Edit `.env` file:

```bash
# Home Assistant
HA_BASE_URL=http://assistant-ha:8123
HA_TOKEN=your_long_lived_access_token

# Timezone
TIME_ZONE=America/Toronto

# Ollama
OLLAMA_HOST=http://hassistant-ollama:11434
```

### Available Models

| Model | Base | Size | Personality | Use Case |
|-------|------|------|-------------|----------|
| `glados-hermes3` | Hermes-3 Llama 3.2 | 3B | Fast, sarcastic | Quick responses |
| `glados-qwen` | Qwen 2.5 | 7B | Detailed, analytical | Complex queries |

Model configurations are in `ollama/modelfiles/`.

## Raspberry Pi Client Setup

The Pi client enables voice interaction from any room.

### Installation

See [PI_SETUP.md](PI_SETUP.md) for complete setup instructions.

Quick setup:
```bash
# On Raspberry Pi
pip install -r requirements.txt  # TODO: create requirements.txt

# Copy environment template
cp pi_client.env.example pi_client.env
# Edit pi_client.env with your configuration

# Run client
python3 pi_client.py
```

### Wake Word Setup

1. Get Porcupine access key from [Picovoice Console](https://console.picovoice.ai/)
2. Add to `pi_client.env`:
   ```bash
   PV_ACCESS_KEY=your_access_key
   WAKE_WORD_MODEL=computer  # or custom .ppn file
   ```

## Documentation

- [Quick Start Guide](QUICK_START.md) - Fast setup walkthrough
- [HA Assist Setup](HA_ASSIST_SETUP.md) - Home Assistant Assist configuration
- [HA Voice Config](HA_VOICE_CONFIG.md) - Voice pipeline setup
- [Wyoming Setup](WYOMING_SETUP.md) - STT/TTS service configuration
- [Memory Integration](MEMORY_INTEGRATION.md) - Memory system usage and API guide
- [Pi Setup](PI_SETUP.md) - Raspberry Pi client setup
- [Pi Ethernet Setup](PI_ETHERNET_SETUP.md) - Network configuration for Pi

## Project Structure

```
HAssistant/
├── docker-compose.yml          # Service orchestration
├── .env                        # Environment configuration
├── ollama/
│   └── modelfiles/             # LLM model definitions
│       ├── Modelfile.hermes3
│       └── Modelfile.qwen
├── pi_client.py               # Raspberry Pi voice client
├── pi_client.env.example      # Pi client config template
├── whisper_data/              # STT model cache (auto-downloaded)
├── piper_data/                # TTS model cache (auto-downloaded)
└── docs/                      # Setup guides
```

## GPU Configuration

The system supports multiple NVIDIA GPUs with automatic allocation:

```yaml
# docker-compose.yml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ['0', '1']  # Both GPUs
          capabilities: [gpu]
```

Ollama automatically distributes model layers across available GPUs for optimal performance.

## Troubleshooting

### Services won't start
```bash
# Check service logs
docker compose logs ollama
docker compose logs whisper
docker compose logs piper

# Verify network exists
docker network ls | grep assistant_default
```

### Models not loading
```bash
# Check Ollama logs
docker logs hassistant-ollama

# Verify GPU access
docker exec hassistant-ollama nvidia-smi

# Manually test model
docker exec -it hassistant-ollama ollama run glados-hermes3 "Hello"
```

### Voice services not working
```bash
# Test Whisper
curl -X POST http://localhost:10300/

# Test Piper
curl http://localhost:10200/

# Check HA integration logs
```

### Pi client issues
See [PI_SETUP.md](PI_SETUP.md) troubleshooting section.

## Performance

With dual GPU setup (GTX 1080 Ti + GTX 1070):
- **Hermes-3 3B**: ~50-100 tokens/sec
- **Qwen 2.5 7B**: ~30-50 tokens/sec
- **Whisper STT**: <1s latency
- **Piper TTS**: <500ms latency

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [Ollama](https://ollama.ai/) - Local LLM runtime
- [Home Assistant](https://www.home-assistant.io/) - Smart home platform
- [Wyoming Protocol](https://github.com/rhasspy/wyoming) - Voice service protocol
- [Porcupine](https://picovoice.ai/platform/porcupine/) - Wake word detection
- GLaDOS voice from Portal
