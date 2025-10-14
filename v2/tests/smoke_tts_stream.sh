#!/usr/bin/env bash
set -euo pipefail

echo "🧪 Testing TTS streaming (L16 PCM)..."

# Test TTS endpoint and capture headers
response=$(curl -sS -X POST http://localhost:8000/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"GLaDOS online. System check nominal."}' \
  --output /tmp/speech_test.pcm -D -)

# Check for L16 content type
if ! echo "$response" | grep -qi 'Content-Type: audio/L16'; then
    echo "❌ TTS streaming failed - wrong content type"
    echo "Headers received:"
    echo "$response"
    exit 1
fi

if ! echo "$response" | grep -qi 'X-TTS-Status: piper'; then
    echo "❌ TTS streaming failed - Piper not in use"
    echo "Headers received:"
    echo "$response"
    exit 1
fi

echo "✅ TTS streaming OK (Piper, L16 PCM format)"
echo "   Output saved to: /tmp/speech_test.pcm"

echo ""
echo "Response headers:"
echo "$response" | grep -iE "(Content-Type|X-Sample-Rate|X-TTS-Status)" || true
