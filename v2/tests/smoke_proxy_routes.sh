#!/usr/bin/env bash
set -euo pipefail

SPEACHES_BASE="${SPEACHES_BASE:-http://localhost:8000}"
WYOMING_BASE="${WYOMING_BASE:-http://localhost:8080}"

curl -fsS "${SPEACHES_BASE}/health" | jq .ok >/dev/null && echo "speaches up ✅"
curl -fsS "${WYOMING_BASE}/healthz" | jq .ok >/dev/null && echo "proxy up ✅"
