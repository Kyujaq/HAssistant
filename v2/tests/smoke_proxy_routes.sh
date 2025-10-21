#!/usr/bin/env bash
set -euo pipefail

WHISPER_BASE="${WHISPER_BASE:-http://localhost:8000}"
WYOMING_BASE="${WYOMING_BASE:-http://localhost:8085}"

curl -fsS "${WHISPER_BASE}/health" | jq .ok >/dev/null && echo "whisper-stt up ✅"
curl -fsS "${WYOMING_BASE}/healthz" | jq .ok >/dev/null && echo "wyoming proxy up ✅"
