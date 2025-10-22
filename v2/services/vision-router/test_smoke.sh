#!/bin/bash
# Smoke tests for vision-router

set -e

HOST="${1:-http://localhost:8050}"

echo "=== Testing vision-router at $HOST ==="

echo -e "\n1. Health check..."
curl -s "$HOST/health" | jq .

echo -e "\n2. Check config..."
curl -s "$HOST/config" | jq .

echo -e "\n3. Check stats (GPU telemetry)..."
curl -s "$HOST/stats" | jq .

echo -e "\n4. Test /events endpoint..."
curl -s -X POST "$HOST/events" \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "screen",
    "ts": 1730000000,
    "frames": [
      {
        "url": "http://example.com/frame1.jpg",
        "width": 1920,
        "height": 1080,
        "ocr": {"text": "Slide 3: Agenda - Q4 Planning", "conf": 0.91}
      }
    ],
    "tags": ["meeting"],
    "detections": []
  }' | jq .

echo -e "\n5. Test /analyze endpoint (ad-hoc)..."
curl -s -X POST "$HOST/analyze" \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "ha_manual",
    "frames": [
      {
        "url": "http://example.com/snapshot.jpg",
        "width": 1920,
        "height": 1080,
        "ocr": {"text": "Dashboard view: Temperature 72°F", "conf": 0.88}
      }
    ],
    "tags": ["dashboard"]
  }' | jq .

echo -e "\n6. Update config (disable escalate_vl)..."
curl -s -X POST "$HOST/config" \
  -H 'Content-Type: application/json' \
  -d '{"escalate_vl": false}' | jq .

echo -e "\n7. Test /events with escalate_vl disabled..."
curl -s -X POST "$HOST/events" \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "screen",
    "ts": 1730000001,
    "frames": [{"url": "http://example.com/frame2.jpg", "ocr": {"text": "High score content"}}],
    "tags": ["meeting"]
  }' | jq .

echo -e "\n8. Re-enable escalate_vl..."
curl -s -X POST "$HOST/config" \
  -H 'Content-Type: application/json' \
  -d '{"escalate_vl": true}' | jq .

echo -e "\n9. Check metrics..."
curl -s "$HOST/metrics" | grep -E "^(vision_events_total|vision_escalations_total|vision_gpu_util|vision_pending_jobs|vision_vl_failovers_total)"

echo -e "\n10. Final stats check..."
curl -s "$HOST/stats" | jq .

echo -e "\n=== All tests completed! ==="
