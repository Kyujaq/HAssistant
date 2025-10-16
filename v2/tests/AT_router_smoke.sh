#!/usr/bin/env bash
# Router Smoke Test - validates intelligent LLM routing
# Usage: bash v2/tests/AT_router_smoke.sh

set -euo pipefail

ORCH=${ORCH:-http://localhost:8020}

echo "🧪 Router Smoke Test"
echo "===================="

# Ensure VL text routing is ON
echo ""
echo "1️⃣  Enabling VL text routing..."
curl -fsS -X POST "$ORCH/router/vl_text_enabled" \
  -H 'Content-Type: application/json' -d '{"enabled": true}' >/dev/null
echo "   ✓ VL routing enabled"

# 1) Fast path -> Hermes
echo ""
echo "2️⃣  Testing fast path (Hermes)..."
FAST=$(curl -fsS -X POST "$ORCH/chat" -H 'Content-Type: application/json' \
  -d '{"input":"What is 2+2?"}' | jq -r '.reply')
echo "   Fast reply: ${FAST:0:80}..."

# 2) Deep path -> VL (or 4B if VL busy)
echo ""
echo "3️⃣  Testing deep path (VL or 4B fallback)..."
DEEP=$(curl -fsS -X POST "$ORCH/chat" -H 'Content-Type: application/json' \
  -d '{"input":"Explain Rayleigh scattering in detail and include wavelength dependence."}' \
  | jq -r '.reply')
echo "   Deep reply: ${DEEP:0:120}..."

# 3) Metrics sanity
echo ""
echo "4️⃣  Checking routing metrics..."
MET=$(curl -fsS "$ORCH/metrics")
echo "$MET" | grep -E 'route_vl_text_hits_total|route_vl_text_fallbacks_total|route_fast_hits_total|route_4b_hits_total' | sed 's/^/   • /'
echo ""
echo "   GPU status:"
echo "$MET" | grep -E 'orchestrator_vl_idle|orchestrator_vl_queue_len' | sed 's/^/   • /'

echo ""
echo "===================="
echo "✅ Router smoke test passed!"
echo ""
