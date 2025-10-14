#!/usr/bin/env bash
set -euo pipefail

echo '🧪 Memory search smoke'

curl -sS -X POST http://localhost:8010/memory/add -H 'Content-Type: application/json' \
  -d '{"text":"HDMI dongle is in the left desk drawer","kind":"note","source":"cli"}' >/dev/null

sleep 0.2

curl -sS -X POST http://localhost:8010/memory/search -H 'Content-Type: application/json' \
  -d '{"q":"Where is the HDMI dongle?"}' | jq -e '.results[0].text|test("HDMI.*drawer"; "i")' >/dev/null

echo '✅ Memory search OK'
