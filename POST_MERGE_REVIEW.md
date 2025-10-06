# Post-Merge System Review

All long-running feature branches are now consolidated on `main`. This review validates the combined architecture, highlights integration points with Home Assistant, and lists the sanity checks you can run to keep the stack healthy.

## High-Level Observations

- The merged stack centers on Home Assistant Assist, with LLM, speech, memory, vision, and automation services fanning out from the Assist pipeline (`docker-compose.yml`).
- Each major capability (Assist core, LLM chat/vision, speech, memory, orchestration, optional desktop control) is represented once—no duplicate containers or overlapping responsibilities.
- Documentation is now aligned with the active service names (`ollama-chat`, `ollama-vision`, etc.), so the Quick Start and troubleshooting steps match the Compose file.

## Integration Map

| Capability | Service(s) | Interface | Notes |
|------------|------------|-----------|-------|
| Assist core | `homeassistant` | Assist / conversation API | Runs on the external `assistant_default` Docker network so it can talk to existing HA add-ons.
| Chat LLM | `ollama-chat` | OpenAI-compatible chat endpoint | Hosts Hermes-3 and Qwen chat models. Shares GPU 0 with `ollama-vision`; models load from `ollama/modelfiles`.
| Vision LLM | `ollama-vision` | OpenAI-compatible multimodal endpoint | Serves Qwen 2.5 VL for the Vision Gateway. GPU 0 placement matches README guidance.
| Speech (STT/TTS) | `whisper`, `piper-glados` | Wyoming protocol | Both containers reserve GPU 1 and expose TCP endpoints Home Assistant can register as Assist providers.
| Memory | `letta-bridge`, `postgres`, `redis` | REST + pgvector | Letta Bridge waits for Postgres/Redis health checks and secures requests with `x-api-key`.
| Orchestration | `glados-orchestrator`, `qwen-agent` | REST/websocket | Routes Assist prompts, streams responses, and syncs memory entries.
| Vision ingress | `vision-gateway`, `frigate`, `frigate-snapshotper` | REST/webhooks | `vision-gateway` pushes anchor-based OCR events into Home Assistant automations.
| Optional desktop control | `computer-control-agent` (commented) | REST/websocket | Disabled by default; depends on Vision Gateway + Ollama chat.

## Configuration Consistency Checks

1. **Environment variables** – `.env.example` now points to `http://ollama-chat:11434`, matching the Compose service and the README instructions.
2. **GPU assignments** – Whisper, Piper, and Frigate stay on GPU 1, while both Ollama containers run on GPU 0 (11 GB), which can host both Hermes-3 and Qwen 2.5 VL simultaneously.
3. **Health checks & dependencies** – Compose health checks ensure Postgres and Redis are ready before Letta Bridge, and that the orchestrator waits for Ollama + Letta Bridge.
4. **Network topology** – All services join the external `assistant_default` network so Home Assistant can resolve them without extra configuration.

## Startup Validation

Run the following sequence after copying `.env.example` → `.env` and editing secrets:

```bash
docker compose pull
docker compose build glados-orchestrator qwen-agent vision-gateway
docker compose up -d

docker compose ps
```

You should see `ollama-chat`, `ollama-vision`, `whisper`, `piper-glados`, `homeassistant`, `letta-bridge`, `glados-orchestrator`, `qwen-agent`, and `vision-gateway` in a `running` state. Optional services (`computer-control-agent`) stay disabled until you uncomment them.

## Manual Smoke Tests

1. **Ollama chat health**
   ```bash
   docker exec -it ollama-chat ollama list
   curl http://localhost:11434/api/tags
   ```
2. **Memory bridge**
   ```bash
   curl -H "x-api-key: ${BRIDGE_API_KEY}" http://localhost:8081/healthz
   ```
3. **Assist round trip**
   - Register Whisper (`tcp://host.docker.internal:10300`) and Piper (`tcp://host.docker.internal:10200`) inside Home Assistant Assist settings.
   - Trigger an Assist conversation and confirm responses appear in HA history with the GLaDOS voice output.
4. **Vision automation (optional)**
   - Confirm Frigate is streaming by visiting `http://localhost:5000`.
   - Open `http://localhost:8088/debug` to view OCR anchors and recent events pushed to HA.

## Outstanding Follow-Ups

- CI: Desktop automation tests (`test_computer_control_agent.py`, Windows clarity scripts) still require additional packages (`pyautogui`, `opencv-python`, etc.) to run headlessly.
- Secrets: Replace all placeholder passwords/API keys in `.env` before deploying and prefer Docker secrets for production.
- Monitoring: Consider adding Prometheus/Grafana exporters if you need telemetry for the expanded stack.

Overall, the merged `main` branch is internally consistent: documentation, compose definitions, and supporting scripts describe the same service layout, and optional components remain isolated behind explicit toggles.
