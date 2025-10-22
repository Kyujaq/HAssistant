#!/bin/bash
# Pull Qwen2.5-VL 7B model for vision-language tasks
# Run this on the main host after bringing up docker-compose.yml

set -e

echo "=== Pulling Qwen2.5-VL 7B model to ollama-vl service ==="

# Ensure ollama-vl is running
if ! docker ps | grep -q hassistant_v2_ollama_vl; then
    echo "ERROR: ollama-vl service is not running"
    echo "Start it first with: cd v2 && docker-compose up -d ollama-vl"
    exit 1
fi

# Pull the model
echo "Pulling qwen2.5vl:7b (this may take several minutes)..."
docker-compose exec ollama-vl ollama pull qwen2.5vl:7b

# Verify the model is available
echo -e "\nVerifying model..."
docker-compose exec ollama-vl ollama list

echo -e "\n✅ Model pull complete!"
echo "The orchestrator is already configured to use qwen2.5vl:7b via OLLAMA_MODEL_VL environment variable"
