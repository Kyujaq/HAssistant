# Debugging the GLaDOS Orchestrator

This guide outlines the process for debugging the `glados-orchestrator` service using Visual Studio Code and a dedicated development Docker Compose file.

## Prerequisites

1.  **Docker**: Ensure Docker is installed and running.
2.  **VS Code**: The editor you are using.
3.  **Python Extension for VS Code**: Make sure the official Microsoft Python extension is installed in VS Code.
4.  **Docker Network**: The `ha_network` (externally named `assistant_default`) must exist. Your main `docker-compose.yml` should already define this. If you ever need to create it manually, use:
    ```bash
    docker network create assistant_default
    ```

## Development Workflow

The development workflow uses a separate Docker Compose file (`docker-compose.dev.yml`) to enable live code reloading and debugging without affecting the main production configuration.

### 1. Start the Development Environment

Instead of `docker compose up`, use the following command to start the services using both the base and the development override file:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This command starts all services but applies the development configuration for `glados-orchestrator`, which includes:
-   Mapping port `5678` for the `debugpy` debugger.
-   Mounting the local `services/glados-orchestrator` directory into the container at `/app`, enabling live code changes.
-   Starting the `uvicorn` server with `--reload` and wrapping it with `debugpy`.

### 2. Attach the VS Code Debugger

Once the container is running, the `glados-orchestrator` will pause and wait for a debugger to attach.

1.  Open the **Run and Debug** panel in VS Code (Ctrl+Shift+D).
2.  Select the **"Attach to GLaDOS Orchestrator"** configuration from the dropdown menu.
3.  Press the **Start Debugging** (F5) button.

The debugger will connect to the `debugpy` instance running inside the container. The application will then finish starting, and you can set breakpoints, inspect variables, and step through the code as you normally would.

### 3. Making Code Changes

Because the local source code is mounted as a volume, any changes you save to files in `services/glados-orchestrator` will be automatically detected by the `uvicorn` server, which will trigger a reload. This allows you to see the effects of your changes instantly without rebuilding the Docker image.

### 4. Stopping the Development Environment

To stop all running services, use the same set of compose files:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

## Home Assistant Logging

To get detailed insight into the requests being sent from Home Assistant to the orchestrator, debugging logs for the `assist_pipeline` and `conversation` components have been enabled in `ha_config/configuration.yaml`.

You can view these logs by following the Home Assistant service:

```bash
docker compose logs -f homeassistant
```

This is particularly useful for diagnosing issues related to entity exposure, conversation flow, and why a specific personality or tool is not being used as expected.
