# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

HAssistant is a voice assistant that layers Home Assistant's Assist API with local LLMs (Ollama), memory (Letta-inspired), and automation services. The system combines voice interaction (Wyoming STT/TTS), GPU-accelerated LLMs, persistent memory with semantic search, and optional vision/computer control agents to deliver a GLaDOS-style experience integrated with Home Assistant.

## Architecture

### High-Level Flow

```
Wake Word → Home Assistant Assist → Ollama (direct) → GLaDOS Orchestrator (tools)
                                         ↓
                                   Letta Bridge (memory)
                                         ↓
                                   PostgreSQL + Redis
```

**Critical Pattern**: Home Assistant connects **directly to Ollama** (port 11434), not to the orchestrator. The orchestrator is a **Tool Provider** that Ollama calls via function calling, not a proxy. This architecture changed in v2.0 (see Orchestrator Refactor below).

### Service Architecture

**Core Services:**
- `homeassistant`: Assist API, automations, dashboard (external `assistant_default` network)
- `ollama-chat` (GPU 1): Hermes-3 (3B, fast) for quick responses
- `ollama-vision` (GPU 0): Qwen2.5-VL (7B vision) for multimodal prompts
- `glados-orchestrator` (port 8082): Tool provider exposing memory, time, HA skills to Ollama
- `letta-bridge` (port 8081): Memory API with 5-tier system and pgvector semantic search
- `whisper` (GPU 1): Wyoming Whisper STT with CUDA acceleration
- `piper-glados` (GPU 1): Wyoming Piper TTS with GLaDOS voice
- `postgres`: pgvector for embeddings, memory schema auto-initialized from `scripts/*.sql`
- `redis`: Session cache and ephemeral data

**Optional Services:**
- `vision-gateway`: HDMI capture, anchor-based OCR, motion detection, Frigate integration
- `frigate` (GPU 1): Webcam motion events and snapshots
- `qwen-agent`: Advanced agent runtime with tool execution (commented out by default)
- `computer-control-agent`: PyAutoGUI automation for remote desktops (commented out)
- Face recognition stack: `double-take`, `compreface-*` services

### GPU Allocation Strategy

**GPU 0 (GTX 1080 Ti - 11GB)**:
- `ollama-vision`: Qwen2.5-VL vision model (~8.6GB)
- Reserves capacity for heavier Qwen 2.5 chat model (7B)

**GPU 1 (GTX 1070)**:
- `ollama-chat`: Hermes-3 (3B, lightweight)
- `whisper`: STT
- `piper-glados`: TTS
- `frigate`: Motion detection

**Rationale**: Hermes-3 stays on the lighter GPU to give room for heavy Qwen models on the 1080 Ti.

## Key Architectural Patterns

### 1. Orchestrator v2.0: Tool Provider Pattern

The orchestrator was refactored from an Ollama API proxy to a tool provider:
- **Old**: HA → Orchestrator (proxy) → Ollama ❌
- **New**: HA → Ollama → Orchestrator (tools) ✅

**Why**: The proxy implementation partially mimicked Ollama's API, breaking model management and causing "unrecognized intent" errors. The tool provider pattern gives HA full Ollama API access while providing specialized tools via function calling.

**Tool Endpoints** (`/tool/`):
- `get_time`: Current date/time in multiple formats
- `letta_query`: Query memory system with semantic search
- `execute_ha_skill`: Execute HA automations/skills

**Tool Discovery**: `GET /tool/list` returns Ollama-compatible function definitions

### 2. Letta Bridge: 5-Tier Memory System

Memory is **opt-in** via the `letta_query` tool (not automatically loaded for all queries).

**Tiers** (auto-eviction policies):
- `session`: Current conversation only
- `short_term`: Recent interactions
- `medium_term`: Important recent context
- `long_term`: Significant memories
- `permanent`: Never evicted (pinned)

**Storage**:
- PostgreSQL with pgvector for semantic search (384-dimensional vectors)
- Redis for session caching
- ✅ **Embeddings**: Letta Bridge uses sentence-transformers (all-MiniLM-L6-v2) for real semantic embeddings
  - Model: all-MiniLM-L6-v2 (~80MB, optimized for semantic search)
  - Dimension: 384 (matches pgvector schema)
  - Performance: ~10-50ms per text on CPU
  - Quality: Excellent for general semantic search

**Database Initialization**: `scripts/*.sql` files auto-run on postgres startup:
1. `01_enable_pgvector.sql`: Enable pgvector extension
2. `02_letta_schema.sql`: Core memory tables
3. `03_legacy_schema.sql`: Backward compatibility
4. `04_indexes.sql`: Performance optimization

### 3. Model Personalities

**Hermes-3** (fast, sarcastic): GLaDOS personality defined in `ollama/modelfiles/Modelfile.hermes3`
- System prompt: "You are GLaDOS, the sarcastic AI from Portal..."
- Use case: Quick responses, conversational queries

**Qwen 2.5** (detailed, analytical): Defined in `ollama/modelfiles/Modelfile.qwen`
- Use case: Complex reasoning, detailed analysis

Models are created with: `docker exec -it ollama-chat ollama create <name> -f /root/.ollama/modelfiles/<file>`

### 4. Vision Gateway: Anchor-Based OCR

Vision Gateway uses **anchor-based detection** (not full-screen OCR) for efficiency:
- `ANCHOR_KEYWORDS`: Specific text to detect (e.g., "Accept", "Send", "Join")
- `CONTEXT_ZONES_ENABLED`: Extract context around detected anchors
- HDMI capture via `/dev/video2` (UGREEN dongle)
- Pushes events to Home Assistant and optionally Computer Control Agent

## Common Development Commands

### Service Management
```bash
# Start all services
docker compose up -d

# View logs (follow)
docker compose logs -f <service>

# Rebuild and restart a service
docker compose build <service>
docker compose restart <service>

# Check service health
docker compose ps
```

### Ollama Model Management
```bash
# List loaded models
docker exec -it ollama-chat ollama list

# Create model from Modelfile
docker exec -it ollama-chat ollama create glados-hermes3 -f /root/.ollama/modelfiles/Modelfile.hermes3

# Test model
docker exec -it ollama-chat ollama run glados-hermes3 "Hello"

# Check GPU usage
docker exec -it ollama-chat nvidia-smi
```

### Testing
```bash
# Test memory API
curl -H "x-api-key: dev-key" http://localhost:8081/healthz

# Test orchestrator tools
curl http://localhost:8082/tool/list
curl http://localhost:8082/tool/get_time

# Run test suites
python3 tests/test_memory_integration.py
python3 tests/test_orchestrator_tools.py
./tests/verify_memory_integration.sh

# Test computer control
python3 examples/example_computer_control.py
```

### Memory Operations
```bash
# Add memory
curl -X POST http://localhost:8081/memory/add \
  -H "x-api-key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "content": "Test memory", "type": "event", "tier": "short"}'

# Search memories
curl "http://localhost:8081/memory/search?q=test&k=5" \
  -H "x-api-key: dev-key"

# Get daily brief
curl "http://localhost:8081/memory/daily_brief?hours=24" \
  -H "x-api-key: dev-key"
```

### Home Assistant Configuration
1. **Add Ollama Integration**:
   - Settings → Devices & Services → Add Integration → Ollama
   - URL: `http://ollama-chat:11434` (direct connection to Ollama, not orchestrator)
   - Model: `hermes3` or `qwen3:4b-instruct-2507-q4_K_M`

2. **Add Wyoming Services**:
   - Whisper STT: `tcp://hassistant-whisper:10300`
   - Piper TTS: `tcp://hassistant-piper-glados:10200`

See `docs/setup/HA_OLLAMA_DIRECT_CONNECTION.md` for tool integration.

## Project Structure

```
HAssistant/
├── services/              # Core microservices
│   ├── glados-orchestrator/   # Tool provider (v2.0, 297 lines)
│   ├── letta-bridge/          # Memory API (5-tier system)
│   ├── vision-gateway/        # HDMI capture, OCR, motion
│   └── pc-control-agent/      # Optional PC automation
├── clients/               # Client scripts
│   ├── pi_client.py           # Raspberry Pi voice client
│   ├── computer_control_agent.py
│   └── windows_voice_control.py
├── docs/                  # Documentation
│   ├── setup/                 # Setup guides
│   ├── architecture/          # Architecture docs
│   └── implementation/        # Feature implementation summaries
├── examples/              # Example scripts
│   ├── example_memory_client.py
│   └── example_ollama_with_tools.py
├── tests/                 # Test suites
├── config/                # Configuration examples (.env.example)
├── scripts/               # Database initialization SQL
├── ollama/modelfiles/     # Model personality definitions
├── ha_config/             # Home Assistant configuration
└── docker-compose.yml     # Service orchestration
```

## Important Configuration Files

### Environment Variables (`.env`)
Copy from `config/.env.example` and set:
- `HA_BASE_URL`: Home Assistant URL
- `HA_TOKEN`: Long-lived access token
- `POSTGRES_PASSWORD`: PostgreSQL password
- `REDIS_PASSWORD`: Redis password
- `BRIDGE_API_KEY`: Letta Bridge API key (default: `dev-key`)
- `TIME_ZONE`: Timezone for time utilities

### Docker Compose (`docker-compose.yml`)
- GPU device assignments via `device_ids: ['0']` or `['1']`
- External network: `assistant_default` (must exist)
- Port mappings to avoid conflicts (e.g., postgres on 5432, redis on 6380)
- Volume mounts for persistent data

### Model Files (`ollama/modelfiles/`)
- `Modelfile.hermes3`: GLaDOS personality for Hermes-3
- `Modelfile.qwen`: Configuration for Qwen 2.5

## Recent Major Changes

### Orchestrator Refactor (v2.0)
**Date**: Recent (see `ORCHESTRATOR_REFACTOR_SUMMARY.md`)

**Changes**:
- Converted from Ollama API proxy to tool provider
- Removed: `OLLAMA_BASE_URL`, `QWEN_MODEL`, `HERMES_MODEL` env vars
- Removed: `/api/chat`, `/api/tags` endpoints (now use Ollama directly)
- Added: `/tool/list`, `/tool/get_time`, `/tool/letta_query`, `/tool/execute_ha_skill`
- Code reduction: 550 lines → 297 lines (46% reduction)
- Performance: ~50ms faster for simple queries (no routing overhead)

**Migration**: Update HA Ollama URL from `http://hassistant-glados-orchestrator:8082` to `http://ollama-chat:11434`

**Documentation**:
- `docs/architecture/ORCHESTRATOR_TOOL_PROVIDER.md`: Full architecture
- `docs/setup/MIGRATION_ORCHESTRATOR_V2.md`: Migration guide
- `QUICK_REFERENCE.md`: Quick reference for v2.0

### Folder Reorganization
**Date**: Recent (see `FOLDER_REORGANIZATION_SUMMARY.md`)

Moved files from root to organized directories:
- Python clients → `clients/`
- Documentation → `docs/` (setup/, architecture/, implementation/)
- Tests → `tests/`
- Config examples → `config/`
- Example scripts → `examples/`
- Services → `services/` (renamed `letta_bridge` → `letta-bridge`)

**Breaking**: Python imports from root will break. Use new paths (e.g., `from clients.computer_control_agent import ...`).

## Troubleshooting

### Services won't start
```bash
# Check logs
docker compose logs <service>

# Verify network exists
docker network ls | grep assistant_default

# Check GPU access
docker exec -it ollama-chat nvidia-smi
```

### Models not loading
```bash
# Check Ollama logs
docker logs ollama-chat

# Verify GPU allocation
docker exec -it ollama-chat nvidia-smi

# List models
docker exec -it ollama-chat ollama list
```

### Memory system issues
```bash
# Check Letta Bridge health
curl -H "x-api-key: dev-key" http://localhost:8081/healthz

# Check postgres connection
docker exec -it hassistant-postgres pg_isready -U hassistant

# Check Redis connection
docker exec -it hassistant-redis redis-cli -a "<password>" ping
```

### Home Assistant integration issues
- Verify HA URL points to `http://ollama-chat:11434` (not orchestrator)
- Check Ollama is reachable from HA: `curl http://ollama-chat:11434/api/tags` from HA container
- Verify models are loaded: `docker exec -it ollama-chat ollama list`
- Check orchestrator health: `curl http://hassistant-glados-orchestrator:8082/healthz`

### Tools not being called
- Verify model supports function calling (Hermes-3+, Qwen 2.5+)
- Check tool definitions: `curl http://hassistant-glados-orchestrator:8082/tool/list`
- Review orchestrator logs: `docker logs hassistant-glados-orchestrator`
- Test tools directly: `curl http://hassistant-glados-orchestrator:8082/tool/get_time`

## Performance Notes

With dual GPU setup:
- **Hermes-3 3B** (GPU 1): ~50-100 tokens/sec
- **Qwen 2.5 7B** (GPU 0): ~30-50 tokens/sec
- **Whisper STT**: <1s latency
- **Piper TTS**: <500ms latency

## Key Documentation References

- `README.md`: Complete project overview
- `docs/architecture/ORCHESTRATOR_TOOL_PROVIDER.md`: Tool provider architecture
- `docs/architecture/MEMORY_INTEGRATION.md`: Memory system details
- `docs/setup/HA_ASSIST_SETUP.md`: Home Assistant Assist configuration
- `docs/setup/HA_OLLAMA_DIRECT_CONNECTION.md`: Ollama integration guide
- `ORCHESTRATOR_REFACTOR_SUMMARY.md`: v2.0 refactor details
- `FOLDER_REORGANIZATION_SUMMARY.md`: Project structure changes
- `QUICK_REFERENCE.md`: Quick reference for orchestrator v2.0
- proactive recommend items that would  be beneficial to add to memory as they come.