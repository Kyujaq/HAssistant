#!/usr/bin/env bash
set -euo pipefail
echo "[custom-glados] ensuring voice metadata" >&2
RUN_SCRIPT="/etc/s6-overlay/s6-rc.d/svc-piper/run"
if grep -q -- '--update-voices' "$RUN_SCRIPT"; then
  sed -i 's/ --download-dir \/config --update-voices/ --download-dir \/config/' "$RUN_SCRIPT"
  echo "[custom-glados] removed --update-voices flag" >&2
fi
python3 - <<'PY'
import json, os, sys
voice_entry = {
    "key": "en_US-glados-medium",
    "name": "glados",
    "quality": "medium",
    "language": {
        "code": "en_US",
        "family": "en",
        "name_native": "English (US)",
        "name_english": "English",
        "country_english": "United States",
    },
    "num_speakers": 1,
    "speaker_id_map": {},
    "files": {
        "en_US-glados-medium.onnx": {
            "size_bytes": 63511038,
            "md5_digest": "a06f8b65ee1e4bf2dfcb0a80b560deeb",
        },
        "en_US-glados-medium.onnx.json": {
            "size_bytes": 7103,
            "md5_digest": "da3df3ba34d9515be5918195d6b3c58c",
        },
    },
    "aliases": ["en_US-glados-high"],
}
voice_key = "en_US-glados-medium"
voices_path = "/config/voices.json"
try:
    with open(voices_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}
except json.JSONDecodeError:
    data = {}
if data.get(voice_key) != voice_entry:
    data[voice_key] = voice_entry
    with open(voices_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print("[custom-glados] voices.json updated", file=sys.stderr)
PY
