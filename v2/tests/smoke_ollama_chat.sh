#!/usr/bin/env bash
set -euo pipefail

OLLAMA_BASE="${OLLAMA_BASE:-http://localhost:11434}"

curl -fsS "${OLLAMA_BASE}/api/version" | jq .version >/dev/null
echo "ollama-chat healthy ✅"
