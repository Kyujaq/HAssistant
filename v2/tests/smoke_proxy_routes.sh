#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://192.168.2.13:8000/health | jq .ok >/dev/null && echo "speaches up ✅"
curl -fsS http://192.168.2.13:10210/healthz | jq .ok >/dev/null && echo "proxy up ✅" || echo "HTTP façade only; proceed"
