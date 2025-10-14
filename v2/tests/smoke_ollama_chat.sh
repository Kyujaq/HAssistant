#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://192.168.2.13:11434/api/tags | jq .models >/dev/null
echo "ollama-chat healthy ✅"
