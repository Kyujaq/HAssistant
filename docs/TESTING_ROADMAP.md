# Feature Testing Roadmap

This roadmap provides a structured sequence for exercising the main features of the HAssistant stack. Each module lists the primary flows to validate along with quick reminders of prerequisites that are easy to overlook before running the test.

## 0. Environment Readiness
1. Validate host resources (GPU availability, CPU load, disk space).
2. Confirm Docker Desktop/Engine is running with the NVIDIA Container Toolkit.
3. Copy `.env.example` files to `.env` (root, `computer_control_agent`, Windows voice control, etc.) and populate required secrets.
4. Run `docker compose pull` and `docker compose build` for fresh images.
5. Start the stack with `docker compose up -d`.

**Quick checklist**
- [ ] `.env` contains Home Assistant URL/token, database credentials, OpenAI-equivalent keys if used.
- [ ] NVIDIA drivers installed and GPUs visible via `nvidia-smi`.
- [ ] Host firewall allows Home Assistant, Wyoming, and Ollama ports on the `assistant_default` network.
- [ ] Optional clients (Pi, Windows laptop) are on the same network and reachable.

## 1. Core Voice Conversation Loop
1. From Home Assistant, open Assist or use the Pi client's wake word to initiate a session.
2. Issue a general knowledge prompt to confirm transcription and response latency.
3. Ask a follow-up that requires short-term context to verify session memory caching.

**Quick checklist**
- [ ] Wyoming Whisper (`whisper`) and Piper (`piper-glados`) containers reporting healthy in `docker compose ps`.
- [ ] Home Assistant Assist integration configured with STT/TTS endpoints.
- [ ] Pi client microphone/speaker working or Assist dashboard microphone allowed in browser.

## 2. LLM Model Switching
1. In Home Assistant, change the Assist prompt target between Hermes-3 (fast, sarcastic) and Qwen3:4b (detailed, analytical).
2. Send identical prompts to compare tone (Hermes-3 GLaDOS personality) versus analytical detail (Qwen).

**Quick checklist**
- [ ] Ollama modelfiles created (`Modelfile.hermes3`, `Modelfile.qwen`) in `ollama/modelfiles/`.
- [ ] Models loaded on `ollama-chat` container: `docker exec -it ollama-chat ollama list` shows Hermes-3 and Qwen3:4b.
- [ ] Vision model loaded on `ollama-vision` container: `docker exec -it ollama-vision ollama list` shows Qwen2.5-VL.
- [ ] GPU allocation correct: `ollama-chat` on GPU 1 (1070), `ollama-vision` on GPU 0 (1080 Ti).

## 3. Memory Bridge Integration
1. Start a conversation that stores a personal detail ("My favorite drink is cold brew").
2. Ask the assistant to recall the detail later in the conversation.
3. Review `letta-bridge` logs or `postgres` tables to confirm embeddings were written.

**Quick checklist**
- [ ] `services/letta-bridge/.env` populated with Postgres, Redis URLs, and JWT secret.
- [ ] `postgres` and `redis` containers healthy and migrations applied (`scripts/*.sql`).
- [ ] `verify_memory_integration.sh` ready to run if deeper validation needed.

## 4. Home Assistant Automations
1. Trigger a voice command mapped to a Home Assistant automation (e.g., toggling a light).
2. Confirm automation history entry is created and the physical/virtual device responds.

**Quick checklist**
- [ ] Relevant Home Assistant entities exposed and not disabled.
- [ ] Automations enabled and referencing the `assist_pipeline` or webhook helpers.
- [ ] Home Assistant token in `.env` has permissions for the targeted domains.

## 5. Raspberry Pi Client (Optional)
1. Deploy `pi_client.py` to the Raspberry Pi and configure `pi_client.env`.
2. Trigger wake word and confirm audio streams to Wyoming services.
3. Validate fallback to Home Assistant Assist if local pathway fails.

**Quick checklist**
- [ ] `pi_client.env` includes MQTT broker details, Assist URL, and wake word settings.
- [ ] USB microphone/speaker mapped correctly (`arecord -l`, `aplay -l`).
- [ ] Python dependencies installed (`pip install -r requirements.txt` for Pi client).

## 6. Vision Gateway and Frigate
1. Start `vision-gateway` and `frigate` containers with camera inputs configured.
2. Trigger motion or present on-screen anchors to generate OCR events.
3. Review Home Assistant notifications or `vision-gateway` logs for detected anchors.

**Quick checklist**
- [ ] Cameras accessible (RTSP/USB) and permissions granted inside containers.
- [ ] Frigate configuration files in `vision-gateway`/`double-take-config` updated with correct stream URLs.
- [ ] Home Assistant long-lived token for vision events stored in `.env`.

## 7. Computer Control Agent
1. Enable the optional `computer-control-agent` service in `docker-compose.yml`.
2. Provide a task that requires desktop automation (e.g., "Open Excel and create a table").
3. Monitor agent output and optional screenshots for successful execution.

**Quick checklist**
- [ ] `computer_control_agent.env` filled with Ollama endpoint, Redis URL, and authentication tokens.
- [ ] Vision Gateway accessible for screen captures; PyAutoGUI dependencies installed.
- [ ] Remote desktop reachable via VNC/RDP if using remote control mode.

## 8. Windows Voice Assistant Bridge
1. Connect the USB audio interface between the orchestrator host and Windows laptop.
2. Start `windows_voice_control.py` with `windows_voice_control.env` populated.
3. Issue commands through Assist and verify they are executed on Windows via TTS playback.

**Quick checklist**
- [ ] Audio routing confirmed (line-in/line-out) and volumes set to avoid clipping.
- [ ] Windows speech recognition configured and calibrated.
- [ ] Correct COM port or HID device IDs specified in env/config files.

## 9. External Tooling via Qwen-Agent (Optional)
1. Enable the `qwen-agent` container and register desired tools in its config.
2. Prompt the assistant with a task requiring tool execution (e.g., REST API call).
3. Confirm tool results appear in the conversation and memory entries are written.

**Quick checklist**
- [ ] Tool API keys (webhooks, REST services) stored securely in agent configuration.
- [ ] `agent_data` volume mounted for persistence.
- [ ] Network routes open to external services being called.

## 10. System Resilience Checks
1. Restart individual containers (e.g., `docker compose restart whisper`) and confirm conversations recover.
2. Simulate network latency or temporarily block Redis/Postgres to observe degradation handling.
3. Review logs for retries, error handling, and alerting paths.

**Quick checklist**
- [ ] Centralized log collection enabled (`docker compose logs -f`).
- [ ] Health checks configured in `docker-compose.yml` for critical services.
- [ ] Alerting hooks (Slack/webhooks) tested if configured.

## 11. Upgrade & Rollback Procedure
1. Pull latest repository changes and rebuild affected services.
2. Run a smoke test of core voice loop and one advanced module (memory or vision).
3. Document any manual migration steps for future reference.

**Quick checklist**
- [ ] Backups created for Postgres, Redis, and configuration volumes.
- [ ] Version tags recorded for Docker images/models prior to upgrade.
- [ ] Release notes drafted capturing test results and outstanding issues.

Following this roadmap ensures every major capability is exercised at least once while highlighting the prerequisites that are often missed during manual testing sessions.
