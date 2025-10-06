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
**Purpose**: Vision processing service for computer control

**Port**: 8088  
**Key Features**:
- Consumes Frigate frames
- OCR with anchor detection
- Screenshot capture API
- Integration with Ollama vision models
- Pushes events to Home Assistant

**Documentation**: See [docs/architecture/COMPUTER_CONTROL_ARCHITECTURE.md](../docs/architecture/COMPUTER_CONTROL_ARCHITECTURE.md)

---

## Service Dependencies

```
┌─────────────────────────────┐
│    Home Assistant Assist    │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│   glados-orchestrator       │
│   (Query Router)            │
└──┬───────────────────┬──────┘
   │                   │
   │              ┌────▼────────┐
   │              │ letta-bridge│
   │              │  (Memory)   │
   │              └─────────────┘
   │
┌──▼───────────┐
│ ollama-chat  │
│  (LLMs)      │
└──────────────┘
```

## Building Services

Each service has its own Dockerfile. To build all services:

```bash
docker compose build
```

To build a specific service:

```bash
docker compose build glados-orchestrator
# or
docker compose build letta-bridge
# or
docker compose build qwen-agent
# or
docker compose build vision-gateway
```

## Configuration

Services are configured via:
1. Environment variables in `docker-compose.yml`
2. `.env` file in repository root (copy from `config/.env.example`)
3. Service-specific configuration files
