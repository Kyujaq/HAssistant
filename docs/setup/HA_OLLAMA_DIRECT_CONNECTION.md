# Home Assistant Configuration for Direct Ollama Connection

## Quick Setup Guide

This guide shows how to configure Home Assistant to connect directly to Ollama while using the GLaDOS Orchestrator as a tool provider.

## Step 1: Configure Ollama Integration

1. Navigate to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for "Ollama Conversation"
4. Configure with these settings:

### Basic Configuration

```yaml
URL: http://ollama-chat:11434
Model: hermes3
Temperature: 0.7
```

### Advanced Settings (Optional)

```yaml
Prompt Template: |
  You are GLaDOS, a sarcastic AI assistant with a dry sense of humor.
  You have access to various tools to help answer questions.
  
  Current conversation:
  {{ messages }}
  
Maximum Tokens: 512
Top P: 0.9
```

## Step 2: Create Conversation Agent

Create a conversation agent that uses Ollama:

1. Go to **Settings → Voice Assistants**
2. Click **Add Assistant**
3. Configure:
   - Name: `GLaDOS`
   - Conversation Agent: `Ollama` (the integration you just added)
   - Speech-to-text: `Whisper`
   - Text-to-speech: `Piper (GLaDOS)`

## Step 3: Test Basic Functionality

Test that Home Assistant can communicate with Ollama directly:

1. Go to **Developer Tools → Services**
2. Select service: `conversation.process`
3. Service data:
```yaml
text: "Hello, who are you?"
agent_id: conversation.glados
```
4. Click **Call Service**

You should see a response from the LLM.

## Step 4: Configure Tool Calling (Advanced)

To enable the Orchestrator's tools, you need to create a custom script or automation that passes tool definitions to Ollama.

### Example: Python Script Component

Create `python_scripts/ollama_with_tools.py`:

```python
"""Call Ollama with tool definitions from Orchestrator"""
import requests
import json

def call_ollama_with_tools(text, agent_id="hermes3"):
    # Get tool definitions from Orchestrator
    orchestrator_url = "http://hassistant-glados-orchestrator:8082"
    tools_response = requests.get(f"{orchestrator_url}/tool/list", timeout=5)
    tools = tools_response.json()["tools"]
    
    # Call Ollama with tools
    ollama_url = "http://ollama-chat:11434"
    response = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": agent_id,
            "messages": [
                {"role": "user", "content": text}
            ],
            "tools": tools,
            "stream": False
        },
        timeout=30
    )
    
    result = response.json()
    message = result.get("message", {})
    
    # Check if LLM wants to call a tool
    if "tool_calls" in message:
        tool_results = []
        for tool_call in message["tool_calls"]:
            function_name = tool_call["function"]["name"]
            arguments = tool_call["function"].get("arguments", {})
            
            # Call the tool on Orchestrator
            tool_url = f"{orchestrator_url}/tool/{function_name}"
            tool_response = requests.post(
                tool_url,
                json=arguments,
                timeout=10
            )
            tool_results.append(tool_response.json())
        
        # Send tool results back to Ollama for final response
        response = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": agent_id,
                "messages": [
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": "", "tool_calls": message["tool_calls"]},
                    {"role": "tool", "content": json.dumps(tool_results)}
                ],
                "stream": False
            },
            timeout=30
        )
        result = response.json()
    
    return result.get("message", {}).get("content", "")

# Make the function available to Home Assistant
text = data.get("text")
agent_id = data.get("agent_id", "hermes3")

response_text = call_ollama_with_tools(text, agent_id)
logger.info(f"Response: {response_text}")

# Set the response as a state attribute
hass.states.set(
    "sensor.ollama_response",
    response_text[:255],  # State max 255 chars
    {"full_response": response_text}
)
```

### Example: Automation to Use Tools

```yaml
automation:
  - alias: "Voice Command with Tools"
    trigger:
      - platform: event
        event_type: assist_pipeline_event
        event_data:
          type: stt_end
    action:
      - service: python_script.ollama_with_tools
        data:
          text: "{{ trigger.event.data.text }}"
          agent_id: "hermes3"
      - service: tts.speak
        data:
          entity_id: tts.piper_glados
          message: "{{ states('sensor.ollama_response') }}"
```

## Step 5: Test Tool Integration

Test a query that should use the `get_time` tool:

```yaml
service: python_script.ollama_with_tools
data:
  text: "What time is it?"
  agent_id: "hermes3"
```

Expected behavior:
1. LLM recognizes need for time information
2. Calls `/tool/get_time` on Orchestrator
3. Receives current time
4. Formats response: "It's 9:30 PM on Tuesday"

## Configuration Examples

### Simple Time Query

```yaml
script:
  ask_time:
    alias: "Ask GLaDOS for the time"
    sequence:
      - service: python_script.ollama_with_tools
        data:
          text: "What time is it?"
      - service: tts.speak
        data:
          entity_id: tts.piper_glados
          message: "{{ state_attr('sensor.ollama_response', 'full_response') }}"
```

### Memory-Enabled Query

```yaml
script:
  ask_with_memory:
    alias: "Ask GLaDOS with memory context"
    sequence:
      - service: python_script.ollama_with_tools
        data:
          text: "What do you remember about my music preferences?"
      - service: tts.speak
        data:
          entity_id: tts.piper_glados
          message: "{{ state_attr('sensor.ollama_response', 'full_response') }}"
```

## Verification Steps

### 1. Verify Ollama Connection

```bash
# From Home Assistant terminal or SSH
curl http://ollama-chat:11434/api/tags
```

Expected: List of available models

### 2. Verify Orchestrator Tools

```bash
curl http://hassistant-glados-orchestrator:8082/tool/list
```

Expected: JSON with tool definitions

### 3. Test Direct Tool Call

```bash
curl http://hassistant-glados-orchestrator:8082/tool/get_time
```

Expected: Current date and time

### 4. Test Ollama with Tools

```bash
curl http://ollama-chat:11434/api/chat -d '{
  "model": "hermes3",
  "messages": [{"role": "user", "content": "What time is it?"}],
  "tools": [{"type": "function", "function": {"name": "get_time", "description": "Get current time", "parameters": {"type": "object", "properties": {}}}}],
  "stream": false
}'
```

Expected: Tool call request or direct response

## Troubleshooting

### Issue: "Model not found" error

**Solution:** 
- Verify model is loaded in Ollama: `docker exec ollama-chat ollama list`
- Pull model if needed: `docker exec ollama-chat ollama pull hermes3`

### Issue: Tools not being called

**Solutions:**
1. Verify model supports function calling (Hermes3, Qwen2.5+)
2. Check tool definitions are properly formatted
3. Ensure tool descriptions are clear and specific
4. Review Ollama logs: `docker logs ollama-chat`

### Issue: Orchestrator unreachable

**Solution:**
- Check orchestrator is running: `docker ps | grep orchestrator`
- Verify network connectivity: `docker exec homeassistant ping hassistant-glados-orchestrator`
- Check health: `curl http://hassistant-glados-orchestrator:8082/healthz`

### Issue: Letta Bridge errors in tools

**Solution:**
- Letta query tool will gracefully degrade if bridge is unavailable
- Check Letta Bridge: `curl -H "x-api-key: dev-key" http://hassistant-letta-bridge:8081/healthz`
- Memory features are optional; other tools will still work

## Performance Tuning

### Optimize for Speed

```yaml
# Lower temperature for faster, more focused responses
Temperature: 0.5

# Reduce max tokens for quicker responses
Maximum Tokens: 256

# Use faster model
Model: hermes3  # 3B parameter model
```

### Optimize for Quality

```yaml
# Higher temperature for more creative responses
Temperature: 0.8

# More tokens for detailed responses
Maximum Tokens: 1024

# Use larger model
Model: qwen3:4b-instruct-2507-q4_K_M  # 4B parameter model
```

## Next Steps

1. **Add Custom Tools**: Extend the Orchestrator with your own tools
2. **Create Automations**: Build voice-controlled automations using tools
3. **Integrate Memory**: Use Letta Bridge for context-aware conversations
4. **Monitor Performance**: Track tool usage and response times

## Resources

- [Ollama Function Calling Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md#chat-request-with-tools)
- [Home Assistant Conversation Integration](https://www.home-assistant.io/integrations/conversation/)
- [GLaDOS Orchestrator Tool Provider Guide](../architecture/ORCHESTRATOR_TOOL_PROVIDER.md)
