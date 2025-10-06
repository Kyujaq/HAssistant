# Services

This directory contains the core microservices that make up HAssistant.

## Service Overview

### glados-orchestrator
**Purpose**: Query routing service that intelligently decides when to use Hermes (personality) vs Qwen (reasoning)

**Port**: 8082  
**Key Features**:
- Routes queries between fast personality model (Hermes) and reasoning model (Qwen)
- Integrates with Letta Bridge for memory
- Supports OpenAI-compatible API endpoints
- Streaming responses

**Documentation**: See [main.py](glados-orchestrator/main.py)

---

### letta-bridge
**Purpose**: Memory API service implementing Letta-style memory architecture

**Port**: 8081  
**Key Features**:
- Tiered memory system (short, long, permanent)
- Semantic search with pgvector
- Redis session caching
- Daily memory briefs
- Memory maintenance endpoints

**Documentation**: See [docs/architecture/MEMORY_INTEGRATION.md](../docs/architecture/MEMORY_INTEGRATION.md)

---

### qwen-agent
**Purpose**: Voice-controlled PC automation agent

**Key Features**:
- Voice command interpretation using Whisper STT
- Natural language understanding with Qwen LLM
- System command execution
- Application control
- Volume and screen control

**Documentation**: See [PC_CONTROL_AGENT.md](qwen-agent/PC_CONTROL_AGENT.md)

---

### vision-gateway
**Purpose**: HDMI capture and vision processing gateway

**Key Features**:
- HDMI capture from UGREEN dongle
- Motion detection
- OCR for UI element detection
- Webhook notifications to Home Assistant
- Teams meeting detection

**Documentation**: See [README.md](vision-gateway/README.md)

---

## Running Services

All services are orchestrated via Docker Compose:

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

## Development

Each service has its own:
- `Dockerfile` - Container definition
- `requirements.txt` - Python dependencies
- `main.py` or equivalent - Main application code

## See Also

- [Main README](../README.md) - Overall project documentation
- [Memory Integration](../docs/architecture/MEMORY_INTEGRATION.md) - Memory architecture
- [Quick Start](../docs/setup/QUICK_START.md) - Setup guide
