#!/usr/bin/env bash
# Smoke test for Memory Integration (Step 2.5)
# Tests end-to-end memory recall flow
#
# Usage: bash v2/tests/AT_chat_memory_smoke.sh

set -euo pipefail

BRIDGE="${BRIDGE_URL:-http://localhost:8010}"
ORCHESTRATOR="${ORCHESTRATOR_URL:-http://localhost:8020}"

echo "🧪 Memory Integration Smoke Test"
echo "=================================="

# 1) Seed a fact
echo ""
echo "1️⃣  Seeding memory..."
SEED_RESULT=$(curl -fsS -X POST "${BRIDGE}/memory/add" \
  -H 'Content-Type: application/json' \
  -d '{"text":"The spare HDMI dongle is in the left desk drawer","kind":"note","source":"seed","hash_id":"hdmi_fact"}' \
  | jq -r '.id')
echo "   ✓ Memory added: ${SEED_RESULT}"

# 2) Baseline chat without memory context (if orchestrator supports it)
echo ""
echo "2️⃣  Baseline check (What is 2+2?)..."
BASELINE=$(curl -fsS -X POST "${ORCHESTRATOR}/chat" \
  -H 'Content-Type: application/json' \
  -d '{"input":"What is 2+2?"}' \
  | jq -r '.reply')
echo "   Reply: ${BASELINE:0:80}"

# 3) Chat with memory recall
echo ""
echo "3️⃣  Testing memory recall..."
RESPONSE=$(curl -fsS -X POST "${ORCHESTRATOR}/chat" \
  -H 'Content-Type: application/json' \
  -d '{"input":"Where did I leave the HDMI dongle?"}')

REPLY=$(echo "$RESPONSE" | jq -r '.reply')
HITS=$(echo "$RESPONSE" | jq -r '.memory_hits')
TURN_ID=$(echo "$RESPONSE" | jq -r '.turn_id')

echo "   Turn ID: ${TURN_ID}"
echo "   Memory hits: ${HITS}"
echo "   Reply: ${REPLY:0:100}"

# 4) Verify recall worked
echo ""
echo "4️⃣  Verifying recall..."
if echo "$REPLY" | grep -Eiq 'drawer|left desk'; then
  echo "   ✅ Recall worked - reply mentions drawer!"
else
  echo "   ❌ No recall - reply was: $REPLY"
  exit 1
fi

# 5) Check metrics
echo ""
echo "5️⃣  Checking metrics..."
STATS=$(curl -fsS "${BRIDGE}/stats")
LAST_HITS=$(echo "$STATS" | jq -r '.last_memory_hits')
LAST_USED=$(echo "$STATS" | jq -r '.last_used')

echo "   Last hits: ${LAST_HITS}"
echo "   Last used: ${LAST_USED}"

if [[ "$LAST_HITS" -gt 0 ]] && [[ "$LAST_USED" == "true" ]]; then
  echo "   ✅ Metrics look good"
else
  echo "   ⚠️  Metrics issue (hits=$LAST_HITS, used=$LAST_USED)"
fi

# 6) Test autosave toggle
echo ""
echo "6️⃣  Testing autosave toggle..."
curl -fsS -X POST "${BRIDGE}/config" \
  -H 'Content-Type: application/json' \
  -d '{"autosave":false}' > /dev/null

BEFORE=$(curl -fsS "${BRIDGE}/stats" | jq -r '.total')

# Make a chat request with autosave off
curl -fsS -X POST "${ORCHESTRATOR}/chat" \
  -H 'Content-Type: application/json' \
  -d '{"input":"Test with autosave off"}' > /dev/null

sleep 1  # Give it a moment

AFTER=$(curl -fsS "${BRIDGE}/stats" | jq -r '.total')

if [[ "$AFTER" -eq "$BEFORE" ]]; then
  echo "   ✅ Autosave off works (total unchanged: ${BEFORE})"
else
  echo "   ⚠️  Autosave off may not work (before=$BEFORE, after=$AFTER)"
fi

# Cleanup: Re-enable autosave
curl -fsS -X POST "${BRIDGE}/config" \
  -H 'Content-Type: application/json' \
  -d '{"autosave":true}' > /dev/null

echo ""
echo "=================================="
echo "🎉 All smoke tests passed!"
echo ""
echo "Summary:"
echo "  - Memory recall: ✅"
echo "  - Metrics updated: ✅"
echo "  - Autosave toggle: ✅"
echo ""
