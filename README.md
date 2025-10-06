# HAssistant - Home Assistant + Ollama Voice Assistant

A complete voice assistant implementation that layers Home Assistant's Assist API with local LLMs, memory, and automation services. The stack combines Ollama, Wyoming STT/TTS, a Letta-inspired memory bridge, and optional vision and computer control agents to deliver a GPU-accelerated GLaDOS-style experience that still plays nicely with the rest of your smart home.

## Features

- **Local LLM Processing**: Ollama with GPU support (GTX 1080 Ti + GTX 1070)
- **Voice Interaction**: Wyoming Whisper (STT) + Piper (TTS) with GLaDOS voice
- **Raspberry Pi Client**: Wake word detection and voice processing
- **PC Control Agent**: Qwen-based voice control for PC operations (NEW!)
- **Home Assistant Integration**: Native Assist API integration
- **Memory System**: Letta Bridge with PostgreSQL + pgvector for contextual memory
- **Dual GPU Support**: Automatic GPU allocation for optimal performance
- **Multiple Models**: Switch between fast (Hermes-3 3B) and detailed (Qwen 2.5 7B) responses
- **Context Awareness**: Redis-backed session caching for multi-turn conversations
- **Computer Control Agent**: Vision-based automation for controlling another computer (Excel, browsers, etc.)
- **Windows Voice Assistant Control**: Control Windows laptops via audio cable and TTS output
- **Home Assistant Assist-first design**: Uses Assist conversations as the primary interface so responses land in HA history and automations.
- **Local LLM processing**: Ollama chat + vision endpoints with GPU scheduling for Hermes-3, Qwen 2.5, and Qwen 2.5 VL models.
- **Voice interaction**: Wyoming Whisper (STT) and Piper (TTS) with switchable voices including the tuned kathleen-high clarity profile for Windows Voice Control.
- **Letta-style memory system**: FastAPI bridge backed by PostgreSQL + pgvector and Redis for semantic recall, daily briefs, and eviction policies.
- **Conversation orchestration**: GLaDOS Orchestrator routes prompts between Hermes (personality) and Qwen (reasoning) while syncing context to memory.
- **Qwen-Agent tooling**: Optional agent runtime wired to Letta Bridge for advanced automation and tool execution.
- **Vision automation**: Vision Gateway + Frigate provide anchored OCR, motion triggers, and screenshot capture for the Computer Control Agent.
- **Computer control workflows**: Automate remote desktops with PyAutoGUI, OCR, or proxy actions through Windows Voice Assistant.
- **Raspberry Pi clients**: Wake-word capture, Assist hand-off, and optional USB-audio bridge for Windows control over 3.5mm links.
- **Dual GPU support**: Compose file pre-allocates dedicated GPUs per workload for predictable latency.

## Branch Readiness Snapshot

| Branch | Status | Summary |
|--------|--------|---------|
| `work` | ✅ Ready for `main` | Aggregates the memory bridge, Qwen/GLaDOS orchestration, computer control, Windows voice clarity updates, and accompanying documentation. The branch is composed entirely of fast-forward merges from the feature PRs in history and is the only active branch in the repository, so it represents the canonical state to ship. |

Recent merge commits show each major feature branch already collapsed into `work`, leaving no divergent histories to reconcile before promoting to `main`. See [MERGE_RECOMMENDATION.md](MERGE_RECOMMENDATION.md) for the latest branch review and promotion guidance.

## Service Inventory

| Capability | Container / Service | Purpose | Key Dependencies |
|------------|---------------------|---------|------------------|
| Assist + Automations | `homeassistant` | Hosts Assist API, automations, and dashboard configuration. | External `assistant_default` Docker network. |
| Chat LLM | `ollama-chat` | Serves Hermes-3, Qwen 2.5 chat models for general dialogue. | NVIDIA GPU 0, modelfiles under `ollama/modelfiles`. |
| Vision LLM | `ollama-vision` | Handles multimodal prompts for the Vision Gateway and computer control workflows. | NVIDIA GPU 0 (11 GB) and the Qwen2.5-VL model. |
| Speech-to-text | `whisper` | Wyoming Whisper server with CUDA acceleration. | NVIDIA GPU 1, `whisper_data` volume. |
| Text-to-speech | `piper-glados` | Wyoming Piper server with GLaDOS and kathleen-high voices. | NVIDIA GPU 1, `piper_data` volume. |
| Memory API | `letta-bridge` | FastAPI bridge for tiered memory, embeddings, and briefs. | `postgres`, `redis`, `.env` secrets. |
| Persistence | `postgres`, `redis` | Store pgvector embeddings + session cache. | `scripts/*.sql` for schema bootstrapping. |
| Conversation router | `glados-orchestrator` | Determines when to use Hermes vs. Qwen, streams responses, syncs memory. | `ollama-chat`, `letta-bridge`. |
| Agent runtime | `qwen-agent` | Optional advanced agent that calls tools via Letta Bridge. | `letta-bridge`, `agent_data` volume (optional). |
| Vision ingress | `vision-gateway` | Consumes Frigate frames, performs OCR with anchors, pushes to HA. | `frigate`, `ollama-vision`, Home Assistant token. |
| Motion capture | `frigate` | Supplies webcam motion events and snapshots to the vision stack. | NVIDIA GPU 1, USB cameras `/dev/video*`. |
| Optional desktop automation | `computer-control-agent` (commented) | Runs PyAutoGUI + OCR tasks or relays to Windows Voice Assistant. | `vision-gateway`, `ollama-chat`, Windows voice cable setup. |

These services are orchestrated through `docker-compose.yml`, and most of them can be toggled on/off depending on which capabilities you need.

## System Flow Overview

1. **Wake & capture**: A Raspberry Pi client or HA microphone triggers Assist, streaming audio to Wyoming Whisper.
2. **Assist prompt**: Home Assistant forwards the transcribed prompt to the GLaDOS Orchestrator which decides whether Hermes alone can answer or whether Qwen reasoning plus Hermes personality is required.
3. **Memory lookup**: The orchestrator and optional Qwen-Agent call the Letta Bridge to retrieve relevant memories, then persist new conversational context after replying.
4. **Response**: Piper generates speech (optionally routed through the Windows clarity profile) which can be played locally, forwarded to the Pi client, or sent over USB audio into a Windows voice session.
5. **Automation hooks**: Vision Gateway + Frigate monitor displays or RTSP feeds, pushing actionable events into HA or the Computer Control Agent for closed-loop automation.

The architecture diagram below highlights the primary Assist → Orchestrator → Memory → Speech loop, while the service inventory shows where optional modules plug in.

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
- [PC Control Agent](qwen-agent/PC_CONTROL_AGENT.md) - Voice-controlled PC operations (NEW!)
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
│   ├── Dockerfile
│   ├── pc_control_agent.py         # Voice-controlled PC agent (NEW!)
│   ├── requirements.txt            # Python dependencies
│   ├── test_pc_control.py          # Test suite
│   └── PC_CONTROL_AGENT.md         # Documentation
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
