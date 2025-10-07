# GLaDOS Orchestrator - Tool Provider Architecture

## Overview

The GLaDOS Orchestrator has been refactored from an Ollama API proxy to a **Tool Provider** for Ollama-based conversation agents. This new architecture allows Home Assistant to connect directly to Ollama while providing specialized tools for memory, time utilities, and Home Assistant skill execution.

## Architecture Changes

### Before (Problematic)
```
Home Assistant → Orchestrator (mimics Ollama) → Ollama
```

**Issues:**
- Orchestrator partially implemented Ollama API, breaking model management
- Home Assistant couldn't list or pull models
- "Unrecognized intent" errors due to incomplete proxy implementation

### After (Fixed)
```
Home Assistant → Ollama (direct connection) → Orchestrator (tool provider)
```

**Benefits:**
- Home Assistant connects directly to Ollama (full API compatibility)
- Orchestrator provides specialized tools via REST endpoints
- Ollama models can call Orchestrator tools using function calling
- Clean separation of concerns
- Easier to maintain and debug

## Available Tools

### 1. `get_time`
Returns the current date and time in multiple formats.

**Endpoint:** `GET/POST /tool/get_time`

**Response:**
```json
{
  "success": true,
  "data": {
    "datetime": "2025-10-07T21:30:00",
    "date": "2025-10-07",
    "time": "21:30:00",
    "day_of_week": "Tuesday",
    "formatted": "Tuesday, October 07, 2025 at 09:30 PM"
  }
}
```

### 2. `letta_query`
Query the Letta memory system for relevant past information.

**Endpoint:** `POST /tool/letta_query`

**Request:**
```json
{
  "query": "user preferences for music",
  "limit": 5
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "user preferences for music",
    "count": 3,
    "memories": [
      {
        "title": "User prefers jazz music",
        "content": "User mentioned enjoying jazz in the evening",
        "tier": "long",
        "created_at": "2025-10-01T10:00:00",
        "score": 0.92
      }
    ]
  }
}
```

### 3. `execute_ha_skill`
Execute a Home Assistant skill or automation.

**Endpoint:** `POST /tool/execute_ha_skill`

**Request:**
```json
{
  "skill_name": "turn_on_lights",
  "parameters": {
    "room": "living_room",
    "brightness": 80
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "skill_name": "turn_on_lights",
    "parameters": {"room": "living_room", "brightness": 80},
    "status": "executed"
  }
}
```

## Tool Definitions

Get all available tools in Ollama function calling format:

**Endpoint:** `GET /tool/list`

**Response:**
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_time",
        "description": "Get the current date and time",
        "parameters": {
          "type": "object",
          "properties": {},
          "required": []
        }
      }
    }
  ],
  "version": "2.0.0",
  "description": "GLaDOS Orchestrator Tool Provider"
}
```

## Configuration

### Home Assistant Setup

1. **Add Ollama Integration**
   - Navigate to: Settings → Devices & Services
   - Click "Add Integration" → Search for "Ollama"
   - Configure:
     - **URL**: `http://ollama-chat:11434` (direct to Ollama)
     - **Model**: `hermes3` or `qwen3:4b-instruct-2507-q4_K_M`

2. **Verify Model Access**
   - In the Ollama integration, you should now see all available models
   - You can pull new models directly from Home Assistant UI

### Ollama Configuration with Tools

To enable function calling with the Orchestrator tools, you need to pass the tool definitions when calling Ollama's `/api/chat` endpoint.

#### Example: Using Tools from Home Assistant

```python
# In Home Assistant automation or script
import requests
import json

# Get tool definitions
tools_response = requests.get("http://hassistant-glados-orchestrator:8082/tool/list")
tools = tools_response.json()["tools"]

# Call Ollama with tools
ollama_response = requests.post(
    "http://ollama-chat:11434/api/chat",
    json={
        "model": "hermes3",
        "messages": [
            {"role": "user", "content": "What time is it?"}
        ],
        "tools": tools,
        "stream": False
    }
)
```

#### Tool Call Flow

1. User asks: "What time is it?"
2. Home Assistant sends query to Ollama with tool definitions
3. Ollama LLM recognizes it needs the `get_time` tool
4. Ollama returns a tool call request
5. Home Assistant (or custom code) calls `/tool/get_time` on the Orchestrator
6. Orchestrator returns the current time
7. Result is sent back to Ollama for final response formatting
8. Ollama returns user-friendly response: "It's 9:30 PM on Tuesday, October 7th, 2025"

## API Endpoints

### Service Endpoints

- `GET /` - Service information and available endpoints
- `GET /healthz` - Health check status
- `GET /tool/list` - List all available tools

### Tool Endpoints

- `GET/POST /tool/get_time` - Get current date and time
- `POST /tool/letta_query` - Query Letta memory system
- `POST /tool/execute_ha_skill` - Execute Home Assistant skill

## Development

### Testing

Run the test suite:
```bash
python3 tests/test_orchestrator_tools.py
```

### Adding New Tools

1. Define the tool in `TOOL_DEFINITIONS`:
```python
{
    "type": "function",
    "function": {
        "name": "my_new_tool",
        "description": "Description of what the tool does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "First parameter"
                }
            },
            "required": ["param1"]
        }
    }
}
```

2. Create the endpoint:
```python
@app.post("/tool/my_new_tool")
async def my_new_tool(request: MyToolRequest):
    try:
        # Implementation
        return ToolResponse(success=True, data=result)
    except Exception as e:
        return ToolResponse(success=False, error=str(e))
```

## Migration from Old Architecture

If you're upgrading from the old orchestrator:

1. **Update Home Assistant Ollama Integration**
   - Change URL from orchestrator to Ollama directly
   - URL: `http://ollama-chat:11434`

2. **Update docker-compose.yml** (if needed)
   - Orchestrator no longer needs to be in the request path
   - Keep orchestrator running for tool support

3. **No Code Changes Required**
   - Old conversation agents will continue to work
   - New tool-based features are opt-in

## Troubleshooting

### Can't see models in Home Assistant
- Verify Home Assistant Ollama integration points to `http://ollama-chat:11434`
- Check Ollama is running: `docker logs ollama-chat`
- Test Ollama directly: `curl http://ollama-chat:11434/api/tags`

### Tools not being called
- Verify tool definitions are included in Ollama requests
- Check Ollama model supports function calling (Hermes3, Qwen2.5+)
- Review orchestrator logs: `docker logs hassistant-glados-orchestrator`

### Letta Bridge connection errors
- Verify Letta Bridge is running: `docker ps | grep letta-bridge`
- Check LETTA_BRIDGE_URL environment variable
- Test directly: `curl -H "x-api-key: dev-key" http://hassistant-letta-bridge:8081/healthz`

## Performance

- Tool endpoints are lightweight and stateless
- Average response time: < 100ms for simple tools
- Letta query depends on memory size and complexity
- No impact on Ollama LLM performance

## Security Considerations

- Tool endpoints should be behind a firewall
- API key authentication for Letta Bridge
- Consider rate limiting for production deployments
- Validate all tool parameters before execution

## Future Enhancements

Planned features:
- Additional HA automation tools
- Weather and calendar integrations
- Custom GLaDOS personality tools
- Tool usage analytics and logging
- Automatic tool discovery for Ollama
