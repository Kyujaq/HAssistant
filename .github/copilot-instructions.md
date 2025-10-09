## HAssistant - AI Agent Onboarding

This guide provides essential information for AI agents to be productive in the HAssistant repository.

### Core Architecture

The system is a voice assistant built around Home Assistant, local LLMs (Ollama), and a suite of microservices orchestrated with `docker-compose.yml`.

**Critical Data Flow:**
1.  **Voice/Text Input** -> **Home Assistant (Assist)**
2.  **Home Assistant** -> **`ollama-chat`** (Directly, at `http://ollama-chat:11434`)
3.  **`ollama-chat`** -> **`glados-orchestrator`** (For specific tools via function calling, at `http://hassistant-glados-orchestrator:8082`)
4.  **`glados-orchestrator`** -> **`letta-bridge`** (For memory operations)
5.  **`letta-bridge`** -> **`postgres`** (pgvector) & **`redis`** (cache)

**Key Architectural Pattern**: Do not route requests from Home Assistant to the `glados-orchestrator`. The orchestrator is **not a proxy**; it is a **tool provider** for Ollama. The primary connection is `HA -> ollama-chat`.

### Service Inventory

- **`homeassistant`**: The central hub for automations and the Assist API. Runs on the external `assistant_default` Docker network.
- **`ollama-chat` / `ollama-vision`**: Serve LLMs. GPU allocation is specified in `docker-compose.yml`.
- **`glados-orchestrator`**: A FastAPI service providing tools to Ollama. Key endpoints are under `/tool/...` (e.g., `/tool/letta_query`, `/tool/get_time`).
- **`letta-bridge`**: The memory API, inspired by Letta/MemGPT. It manages a tiered memory system.
- **`whisper` / `piper-glados`**: Wyoming-based STT and TTS services.
- **`postgres`**: Database using `pgvector` for semantic memory search. Schema is initialized from files in `scripts/`.
- **`vision-gateway`**: Optional service for vision-based automation, consuming feeds from `frigate`.
- **`computer-control-agent`**: Optional agent for desktop automation using `PyAutoGUI`.

### Developer Workflow

**1. Environment Setup:**
- Copy `config/.env.example` to `.env` in the project root.
- Populate `.env` with your `HA_BASE_URL`, `HA_TOKEN`, and other secrets.
- Ensure the Docker network `assistant_default` exists: `docker network create assistant_default`.

**2. Running the System:**
- Start all services: `docker compose up -d`
- View logs for a specific service: `docker compose logs -f <service_name>` (e.g., `glados-orchestrator`)
- Rebuild a service after changes: `docker compose build <service_name> && docker compose up -d --force-recreate <service_name>`

**3. Managing LLM Models:**
- Models are defined in `ollama/modelfiles/`.
- Load a model into Ollama: `docker exec -it hassistant-ollama-chat ollama create <model-name> -f /root/.ollama/modelfiles/<modelfile-name>`
- List running models: `docker exec -it hassistant-ollama-chat ollama list`

**4. Testing:**
- **Memory Service**: Test the `letta-bridge` health endpoint. It requires an API key.
  ```bash
  curl -H "x-api-key: dev-key" http://localhost:8081/healthz
  ```
- **Orchestrator Tools**: Check the available tools.
  ```bash
  curl http://localhost:8082/tool/list
  ```
- **Python Tests**: Run the test suites located in the `tests/` directory.
  ```bash
  python3 -m pytest tests/
  ```

### Key Conventions & Patterns

- **Configuration**: All services are configured via environment variables defined in the root `.env` file and passed through `docker-compose.yml`.
- **Database Schema**: The `postgres` database schema is automatically created and updated from the `.sql` files in the `scripts/` directory on startup. To make schema changes, edit those files.
- **Memory System (`letta-bridge`)**:
    - This service uses a 5-tier memory architecture (session, short, medium, long, permanent).
    - **IMPORTANT**: The current implementation uses `fake_embed()` to generate random vectors for embeddings. For any production or meaningful semantic search, this function in `services/letta-bridge/main.py` must be replaced with a real sentence-transformer model.
- **Client Scripts**: Reusable client logic is located in the `clients/` directory (e.g., `pi_client.py`, `computer_control_agent.py`).
- **Documentation**: The `docs/` directory is the source of truth. Architecture documents in `docs/architecture/` are particularly important for understanding the "why" behind the system's design.

### Project Structure Overview

- `docker-compose.yml`: Defines all services and their relationships. **Start here.**
- `services/`: Source code for each microservice (`glados-orchestrator`, `letta-bridge`, etc.).
- `clients/`: Python scripts for interacting with the services (e.g., Raspberry Pi client).
- `config/`: Example environment files (`.env.example`).
- `scripts/`: SQL files for database initialization.
- `ollama/modelfiles/`: Definitions for custom LLM personalities (e.g., GLaDOS).
- `docs/`: All project documentation.
- `tests/`: Automated tests for services.
- `examples/`: Standalone scripts demonstrating features.
