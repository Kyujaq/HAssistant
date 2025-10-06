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
- **Context Awareness**: Redis-backed session caching for multi-turn conversations
- **Computer Control Agent**: Vision-based automation for controlling another computer (Excel, browsers, etc.)
- **Windows Voice Assistant Control**: Control Windows laptops via audio cable and TTS output

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
│  LLM  │ │ Services│ │ + Postgres │
└───────┘ └─────────┘ └─────┬───────┘
                            │
                      ┌─────▼─────┐
                      │   Redis   │  Session cache
                      └───────────┘
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

### 5. Test Memory Integration (Optional)

The memory system is automatically integrated and running. Test it:

```bash
# Run the example client (requires requests library)
pip install requests
python3 example_memory_client.py

# Or test via curl
curl -X GET http://localhost:8081/healthz

# Add a test memory
curl -X POST http://localhost:8081/memory/add \
  -H "x-api-key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Memory",
    "content": "This is a test memory entry",
    "type": "event",
    "tier": "short"
  }'
```

See [MEMORY_INTEGRATION.md](MEMORY_INTEGRATION.md) for complete memory system documentation.

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

## Computer Control Agent

The Computer Control Agent enables automated control of another computer using vision and AI. Perfect for automating tasks in Excel, browsers, and other GUI applications.

See [COMPUTER_CONTROL_AGENT.md](COMPUTER_CONTROL_AGENT.md) for complete documentation.

Quick setup:
```bash
# Install dependencies
pip install -r computer_control_requirements.txt

# Install Tesseract OCR (Ubuntu/Debian)
sudo apt-get install tesseract-ocr

# Copy configuration
cp computer_control_agent.env.example computer_control_agent.env
# Edit configuration as needed

# Run a task
python computer_control_agent.py --task "Open notepad"
```

Features:
- Vision-based screen understanding with OCR
- AI-powered decision making via Ollama
- Support for Excel, browsers, and desktop apps
- Safe execution with confirmations and failsafes
- Remote control via vision-gateway integration
- **NEW: Windows Voice Control integration** - Use Windows Voice Assistant for command execution

### Computer Control + Windows Voice Integration

The Computer Control Agent can now execute commands via Windows Voice Assistant, combining AI-powered vision and decision making with voice-based execution.

See [COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md](COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md) for complete integration guide.

Quick usage:
```bash
# Enable Windows Voice mode via environment variable
export USE_WINDOWS_VOICE=true

# Or use command line flag
python computer_control_agent.py --windows-voice --task "Open Notepad and type Hello"
```

This integration provides:
- AI-powered computer control with Windows Voice Assistant execution
- No software installation needed on Windows (uses built-in Voice Assistant)
- Physical separation via audio cable for enhanced security
- Flexible mode switching between direct control and voice control

## Windows Voice Assistant Control

Control Windows laptops using Windows Voice Assistant by routing Piper TTS audio through a USB audio dongle via 3.5mm aux cable.

See [WINDOWS_VOICE_ASSIST_SETUP.md](WINDOWS_VOICE_ASSIST_SETUP.md) for complete setup guide.

Quick setup:
```bash
# Configure USB audio device
export USB_AUDIO_DEVICE=hw:1,0  # Your USB dongle

# Enable clearer voice for better recognition (recommended)
export USE_DIRECT_PIPER=true
export PIPER_VOICE_MODEL=en_US-kathleen-high
export PIPER_LENGTH_SCALE=1.1

# Use the USB audio version of pi_client
cp pi_client_usb_audio.py pi_client.py

# Or use the standalone control script
python3 windows_voice_control.py "Open Notepad"
```

Features:
- Control Windows via audio cable (no software installation needed)
- Works with built-in Windows Voice Assistant/Cortana
- Simple hardware setup (USB audio dongle + aux cable)
- Integration with Home Assistant voice pipeline
- **NEW:** Clearer kathleen-high voice for improved recognition (reduces misunderstandings)
- **NEW:** Adjustable speech speed and volume for optimal clarity

For voice clarity optimization, see [WINDOWS_VOICE_CLARITY_GUIDE.md](WINDOWS_VOICE_CLARITY_GUIDE.md).

### Wake Word Setup

1. Get Porcupine access key from [Picovoice Console](https://console.picovoice.ai/)
2. Add to `pi_client.env`:
   ```bash
   PV_ACCESS_KEY=your_access_key
   WAKE_WORD_MODEL=computer  # or custom .ppn file
   ```

## Memory Integration

HAssistant includes a sophisticated memory system inspired by Letta (formerly MemGPT) for persistent, context-aware AI interactions.

### Features

- **Tiered Memory**: 5-tier system (session, short-term, medium-term, long-term, permanent)
- **Semantic Search**: Vector embeddings with pgvector for context-aware memory recall
- **Automatic Eviction**: Time-based cleanup with pin protection for important memories
- **REST API**: FastAPI service for memory operations (add, search, pin, forget)
- **Daily Briefing**: Automatic summaries of important recent memories

### Quick Start

```bash
# Memory API is available at http://localhost:8081
# Test the health endpoint
curl -H "x-api-key: dev-key" http://localhost:8081/healthz

# Add a memory
curl -X POST http://localhost:8081/memory/add \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-key" \
  -d '{
    "type": "fact",
    "title": "User prefers GLaDOS personality",
    "content": "User likes sarcastic, witty responses",
    "tier": "long",
    "pin": true
  }'

# Search memories semantically
curl "http://localhost:8081/memory/search?q=personality&k=5" \
  -H "x-api-key: dev-key"
```

### Architecture

- **Letta Bridge** (Port 8081): FastAPI service with memory endpoints
- **PostgreSQL + pgvector**: Persistent storage with vector similarity search
- **Redis**: Session caching and ephemeral data
- **Database Schemas**: Automatic initialization via SQL scripts

See [MEMORY_INTEGRATION.md](MEMORY_INTEGRATION.md) for complete documentation.

## Documentation

- [Quick Start Guide](QUICK_START.md) - Fast setup walkthrough
- [Memory Integration](MEMORY_INTEGRATION.md) - Letta-style memory system documentation
- [HA Assist Setup](HA_ASSIST_SETUP.md) - Home Assistant Assist configuration
- [HA Voice Config](HA_VOICE_CONFIG.md) - Voice pipeline setup
- [Wyoming Setup](WYOMING_SETUP.md) - STT/TTS service configuration
- [Pi Setup](PI_SETUP.md) - Raspberry Pi client setup
- [Pi Ethernet Setup](PI_ETHERNET_SETUP.md) - Network configuration for Pi
- [Computer Control Agent](COMPUTER_CONTROL_AGENT.md) - Vision-based automation
- [Computer Control Quick Start](COMPUTER_CONTROL_QUICK_START.md) - Fast setup for computer control
- [Windows Voice Assistant Setup](WINDOWS_VOICE_ASSIST_SETUP.md) - Control Windows via audio cable

## Project Structure

```
HAssistant/
├── docker-compose.yml              # Service orchestration
├── .env                            # Environment configuration
├── .env.example                    # Environment template
├── letta_bridge/                   # Memory API service
│   ├── Dockerfile
│   ├── main.py                     # FastAPI endpoints
│   └── requirements.txt
├── scripts/                        # Database initialization
│   ├── 01_enable_pgvector.sql
│   ├── 02_letta_schema.sql         # Core memory tables
│   ├── 03_legacy_schema.sql        # Backward compatibility
│   └── 04_indexes.sql              # Performance optimization
├── ollama/
│   └── modelfiles/                 # LLM model definitions
│       ├── Modelfile.hermes3
│       └── Modelfile.qwen
├── glados-orchestrator/            # Query routing service
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── qwen-agent/                     # AI orchestration service
│   └── Dockerfile
├── vision-gateway/                 # Vision processing service
│   ├── Dockerfile
│   └── app/main.py
├── ha_config/                      # Home Assistant configuration
│   ├── configuration.yaml          # Includes memory REST commands
│   └── automations.yaml            # Memory automation examples
├── pi_client.py                    # Raspberry Pi voice client
├── pi_client.env.example           # Pi client config template
├── example_memory_client.py        # Python client example
├── test_memory_integration.py      # Memory API test suite
├── whisper_data/                   # STT model cache (auto-downloaded)
├── piper_data/                     # TTS model cache (auto-downloaded)
└── docs/                           # Setup guides
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
