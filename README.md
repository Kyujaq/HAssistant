# HAssistant - Home Assistant + Ollama Integration

Clean implementation of GLaDOS using Home Assistant native features and Ollama for local LLM support.

## Quick Start

```bash
# Start Ollama
docker compose up -d

# Load models
docker exec -it hassistant-ollama ollama create glados-hermes3 -f /root/.ollama/modelfiles/Modelfile.hermes3
docker exec -it hassistant-ollama ollama create glados-qwen -f /root/.ollama/modelfiles/Modelfile.qwen

# Verify models
docker exec -it hassistant-ollama ollama list
```

## Architecture

- **Ollama**: Local LLM server with GPU support (both GPUs available)
- **Home Assistant**: Central automation and integration hub
- **Models**:
  - `glados-hermes3` (Hermes-3 Llama 3.2 3B) - Fast, sarcastic responses
  - `glados-qwen` (Qwen 2.5 7B) - Detailed, analytical responses

## Home Assistant Integration

1. Navigate to Settings → Devices & Services
2. Add Integration → Search for "Ollama"
3. Configure:
   - URL: `http://hassistant-ollama:11434`
   - Model: `glados-hermes3` (or `glados-qwen`)
4. Use in automations, voice assistants, and conversation agents

## GPU Setup

- GTX 1080 Ti (11GB) + GTX 1070 (8GB)
- Automatic GPU allocation via Ollama
- All model layers offloaded to GPU (`num_gpu: 99`)
