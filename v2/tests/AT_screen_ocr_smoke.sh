#!/usr/bin/env bash
set -euo pipefail

ROUTER=${ROUTER:-http://k80-vm:8050}

echo "🧪 Screen OCR → vision-router smoke"
curl -fsS -X POST "$ROUTER/events" -H 'Content-Type: application/json' -d @- <<'JSON' | jq .
{
  "source": "screen",
  "ts": 1730000001,
  "frames": [
    {
      "url": "http://example/frames/slide1.jpg",
      "ocr": {
        "text": "Sprint Review - Summary\nVelocity 42, Bugs 5, Next Steps",
        "conf": 0.84
      }
    }
  ],
  "detections": [
    {
      "label": "screen",
      "conf": 0.91
    }
  ],
  "tags": [
    "slide_candidate"
  ],
  "meta": {
    "host": "vm-k80"
  }
}
JSON

curl -fsS "$ROUTER/metrics" | grep -E 'vision_events_total|vision_escalations_total'
echo "✅ Screen smoke OK"
