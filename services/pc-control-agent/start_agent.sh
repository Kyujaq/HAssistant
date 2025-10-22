#!/bin/bash
# Quick start script for Qwen PC Control Agent

echo "🚀 Starting Qwen PC Control Agent..."
echo ""
echo "Prerequisites:"
echo "  1. Whisper STT running (default: http://hassistant-whisper:10300)"
echo "  2. Ollama with Qwen model (default: http://ollama-chat:11434)"
echo "  3. Microphone connected"
echo ""

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running in Docker container"
    cd /app
else
    echo "Running standalone"
    cd "$(dirname "$0")"
fi

# Check dependencies
echo "Checking dependencies..."
python3 -c "import pyaudio, numpy, requests, psutil" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Installing..."
    pip install -r requirements.txt
fi

# Set environment variables if not set
export WHISPER_STT_URL=${WHISPER_STT_URL:-http://hassistant-whisper:10300}
export OLLAMA_URL=${OLLAMA_URL:-http://ollama-chat:11434}
export QWEN_MODEL=${QWEN_MODEL:-qwen2.5:7b}

echo ""
echo "Configuration:"
echo "  STT: $WHISPER_STT_URL"
echo "  LLM: $OLLAMA_URL"
echo "  Model: $QWEN_MODEL"
echo ""

# Test connectivity
echo "Testing services..."
curl -s -m 5 "$WHISPER_STT_URL" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Whisper STT is reachable"
else
    echo "⚠️  Warning: Cannot reach Whisper STT at $WHISPER_STT_URL"
fi

curl -s -m 5 "$OLLAMA_URL/api/tags" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Ollama is reachable"
else
    echo "⚠️  Warning: Cannot reach Ollama at $OLLAMA_URL"
fi

echo ""
echo "Starting agent..."
echo "Press Ctrl+C to exit"
echo ""

python3 pc_control_agent.py
