# Crew Orchestrator Service

Excel task automation service using the CrewAI framework for intelligent UI automation.

## Overview

The Crew Orchestrator service provides an API endpoint for automating Excel tasks through natural language commands. It uses CrewAI agents to plan, execute, and verify UI automation tasks.

## Architecture

The service consists of three main AI agents:

1. **UI Automation Planner**: Decomposes high-level goals into step-by-step action plans
2. **UI Action Agent**: Executes voice commands via Windows Voice Control
3. **Screen State Verifier**: Validates actions using vision-based verification

## API Endpoints

### Root Endpoint
```
GET /
```
Returns service information and available endpoints.

**Response:**
```json
{
  "service": "Crew Orchestrator",
  "version": "1.0.0",
  "status": "operational",
  "endpoints": {
    "health": "/healthz",
    "kickoff": "/crew/excel/kickoff"
  }
}
```

### Health Check
```
GET /healthz
```
Returns health status of the service and its components.

**Response:**
```json
{
  "ok": true,
  "service": "crew-orchestrator",
  "agents": {
    "planner": "initialized",
    "action_agent": "initialized",
    "verification_agent": "initialized"
  },
  "tools": {
    "voice_command": "initialized",
    "vision_verification": "initialized"
  }
}
```

### Kickoff Excel Task
```
POST /crew/excel/kickoff
```
Initiates an Excel automation task based on a natural language goal.

**Request Body:**
```json
{
  "goal": "Create a new spreadsheet with sales data"
}
```

**Response:**
```json
{
  "status": "success",
  "goal": "Create a new spreadsheet with sales data",
  "result": "Step-by-step plan with voice commands and verification queries"
}
```

**Validation:**
- `goal` must be 1-500 characters
- `goal` cannot be empty or whitespace only

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8084` | Service port |
| `WINDOWS_VOICE_CONTROL_URL` | `http://localhost:8085` | Windows voice control service URL |
| `VISION_GATEWAY_URL` | `http://vision-gateway:8088` | Vision verification service URL |

## Integration

### Home Assistant Configuration

Add to your Home Assistant `configuration.yaml`:

```yaml
rest_command:
  crew_excel_task:
    url: http://hassistant-crew-orchestrator:8084/crew/excel/kickoff
    method: POST
    headers:
      accept: "application/json"
      content-type: "application/json"
    payload: '{"goal": "{{ goal }}"}'
```

### Usage Example

```bash
# Test the service
curl -X POST http://localhost:8084/crew/excel/kickoff \
  -H "Content-Type: application/json" \
  -d '{"goal": "Open Excel and create a new worksheet"}'
```

## Dependencies

The service is designed to integrate with external services:

1. **Windows Voice Control** (`windows_voice_control.py`)
   - Standalone Python script for voice command execution
   - Uses TTS (Piper) to send audio commands via USB audio cable
   - Currently called as a standalone script, not as a service endpoint
   - Located in the root directory of the project

2. **Vision Gateway Service** (`vision-gateway`)
   - Tracks UI elements via HDMI capture
   - Provides `/ingest_frame` and `/poll_tracking` endpoints
   - Designed for button/element state tracking rather than general Q&A
   - Note: The current placeholder implementation assumes a `/query` endpoint which doesn't exist yet

### Integration Notes

**Current Implementation Status:**
- Voice commands are routed through the shared `WindowsVoiceExecutor`, which attempts to call the Windows
  Voice Control HTTP service and gracefully falls back to the local Python implementation
- Vision verification questions are answered using live data from the `vision-gateway` service, leveraging its
  meeting invite detection and button press heuristics

**Recommended Next Steps:**
1. Expand the vision heuristics to cover additional UI validation scenarios
2. Persist verification transcripts for later review

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py
```

### Running with Docker

```bash
# Build the image
docker build -t crew-orchestrator .

# Run the container
docker run -p 8084:8084 \
  -e WINDOWS_VOICE_CONTROL_URL=http://host:8085 \
  -e VISION_GATEWAY_URL=http://host:8088 \
  crew-orchestrator
```

### Testing

```bash
# Health check
curl http://localhost:8084/healthz

# Test task execution
curl -X POST http://localhost:8084/crew/excel/kickoff \
  -H "Content-Type: application/json" \
  -d '{"goal": "Test task"}'
```

## Current Status

### Implemented
- ✅ FastAPI service structure
- ✅ CrewAI agent definitions
- ✅ Input validation
- ✅ Error handling
- ✅ Health checks
- ✅ Logging

### In Progress / TODO
- ✅ **Windows Voice Control Integration**: Shared executor calls the HTTP service and falls back to the local bridge
- ✅ **Vision Gateway Integration**: Verification tool consumes live detections from `vision-gateway`
- ⚠️ **Full Task Execution**: Currently only plans tasks, needs execution loop
- ⚠️ **Task History**: Store and retrieve past executions
- ⚠️ **Progress Tracking**: Real-time updates on task progress

## Troubleshooting

### Service not starting
- Check that port 8084 is available
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check logs for initialization errors

### Tasks failing
- Verify Windows Voice Control service is running
- Verify Vision Gateway service is running
- Check service URLs in environment variables
- Review logs for detailed error messages

## License

Part of the HAssistant project. See root LICENSE file for details.
