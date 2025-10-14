#!/usr/bin/env bash
set -euo pipefail
cid=$(docker compose -f v2/docker-compose.yml ps -q ollama-chat)
[ -n "$cid" ] || { echo "ollama-chat not running"; exit 1; }
docker exec -it "$cid" bash -lc '
    set -e
    ollama pull hermes3 || true
    ollama pull qwen:3.4b || true
    ollama list
'
