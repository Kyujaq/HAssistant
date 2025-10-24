# Docker Compose Guide

## Main Services (`docker-compose.yml`)

Start all production services:
```bash
docker compose up -d
```

All services in the main compose file have auto-restart policies:
- `restart: on-failure:3` - Restart up to 3 times on failure
- `restart: unless-stopped` - Always restart unless manually stopped

### Service Categories

**Core Services** (always running):
- `ollama-text`, `ollama-vl` - LLM inference
- `whisper-stt` - Speech-to-text
- `piper-main`, `wyoming-piper` - Text-to-speech
- `wyoming_openai` - Wyoming protocol bridge
- `postgres`, `redis` - Databases
- `memory-embed` - Memory embeddings
- `letta-server` - Memory/agent runtime
- `orchestrator` - Main orchestrator service
- `s2p-gate` - Fast command routing

**Support Services**:
- `mosquitto` - MQTT broker
- `tailscale` - VPN
- `mediamtx` - Media streaming
- `dozzle` - Log viewer (port 9999)
- `prometheus`, `grafana`, `alertmanager` - Monitoring
- `searxng`, `readability`, `doc-index` - Search/docs
- `smi2mqtt` - GPU stats to MQTT

## One-Time Setup Services (`docker-compose.setup.yml`)

Run these **manually** when needed (not on every startup):

### Memory Migrations
Applies database schema changes:
```bash
docker compose -f docker-compose.setup.yml up memory-migrations
```

### Memory Backfill
Imports historical memory data (from v1 or sample data):
```bash
docker compose -f docker-compose.setup.yml up memory-backfill
```

**Note**: These services have `restart: "no"` and will only run when explicitly started.

## Common Commands

### Start everything
```bash
cd /home/qjaq/HAssistant/v2
docker compose up -d
```

### Check status
```bash
docker compose ps
```

### View logs
```bash
docker compose logs -f orchestrator
docker compose logs -f letta-server
```

### Restart a service
```bash
docker compose restart orchestrator
```

### Stop everything
```bash
docker compose down
```

### Rebuild and restart a service
```bash
docker compose build orchestrator
docker compose restart orchestrator
```

## Auto-Start on Reboot

Docker services with `restart: on-failure:3` or `restart: unless-stopped` will automatically start when Docker daemon starts after a reboot.

If services don't start after reboot:
1. Check Docker daemon is running: `sudo systemctl status docker`
2. Start Docker if needed: `sudo systemctl start docker`
3. Check service health: `docker compose ps`
4. View logs: `docker compose logs <service>`
