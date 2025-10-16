#!/usr/bin/env bash
set -euo pipefail

ROUTER=${ROUTER:-http://k80-vm:8050}

echo "🧪 Frigate → vision-router smoke"
curl -fsS -X POST "$ROUTER/events" -H 'Content-Type: application/json' -d @- <<'JSON' | jq .
{
  "source": "camera.office",
  "ts": 1730000000,
  "frames": [
    {
      "url": "http://example/frames/f1.jpg",
      "ocr": {
        "text": "Project Update - Agenda\nRoadmap, Risks, Action Items",
        "conf": 0.86
      }
    }
  ],
  "detections": [
    {
      "label": "screen",
      "conf": 0.93
    }
  ],
  "tags": [
    "meeting",
    "slide_candidate"
  ],
  "meta": {
    "zone": "office"
  }
}
JSON

curl -fsS "$ROUTER/metrics" | grep -E 'vision_events_total|vision_escalations_total'
echo "✅ Frigate smoke OK"
