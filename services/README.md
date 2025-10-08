# Services

This directory contains the core microservices that make up HAssistant.

## Service Overview

### glados-orchestrator
**Purpose**: Tool provider service for Ollama LLM function calling

**Port**: 8082  
**Architecture**: Home Assistant → Ollama → Orchestrator (tools)

**Key Features**:
- RESTful tool endpoints for LLM function calling
- Memory integration via Letta Bridge (`/tool/letta_query`)
- Time and date utilities (`/tool/get_time`)
- Home Assistant skill execution (`/tool/execute_ha_skill`)
- Lightweight, stateless design

**Documentation**: See [ORCHESTRATOR_TOOL_PROVIDER.md](../docs/architecture/ORCHESTRATOR_TOOL_PROVIDER.md) and [HA_OLLAMA_DIRECT_CONNECTION.md](../docs/setup/HA_OLLAMA_DIRECT_CONNECTION.md)

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
           │ (direct connection)
           ▼
┌──────────────────────────────┐
│       ollama-chat            │
│       (LLMs)                 │
└──┬───────────────────────────┘
   │
   │ (function calling)
   │
   ▼
┌──────────────────────────────┐
│   glados-orchestrator        │
│   (Tool Provider)            │
└──┬───────────────────────────┘
   │
   │ (memory queries)
   ▼
┌──────────────────────────────┐
│      letta-bridge            │
│      (Memory)                │
└──────────────────────────────┘
```

**Key Architecture Change**: Home Assistant now connects directly to Ollama instead of through the orchestrator. The orchestrator provides specialized tools that Ollama can call via function calling.

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
