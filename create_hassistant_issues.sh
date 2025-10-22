#!/usr/bin/env bash
set -euo pipefail

REPO="Kyujaq/HAssistant"   # change if you fork

# --- Labels ---------------------------------------------------------------
declare -A LABELS=(
  ["type:feat"]="#1E90FF"
  ["type:task"]="#A9A9A9"
  ["type:bug"]="#DC143C"
  ["priority:P1"]="#FF4500"
  ["priority:P2"]="#FFA500"
  ["priority:P3"]="#32CD32"
  ["area:vision"]="#5F9EA0"
  ["area:voice"]="#9370DB"
  ["area:planner"]="#2E8B57"
  ["service:memory"]="#20B2AA"
  ["service:orchestrator"]="#00CED1"
  ["integration:ha"]="#228B22"
  ["integration:paprika"]="#8B4513"
  ["infra:compose"]="#708090"
  ["docs"]="#000000"
  ["testing"]="#696969"
)

echo "Creating labels (idempotent)…"
for name in "${!LABELS[@]}"; do
  color=${LABELS[$name]#\#}
  gh label create "$name" --color "$color" --repo "$REPO" 2>/dev/null || true
done

create_issue() {
  local title="$1"; shift
  local body="$1"; shift
  local labels="$1"; shift
  gh issue create --repo "$REPO" --title "$title" --body "$body" --label $labels
}

# --- Issues ---------------------------------------------------------------

read -r -d '' BODY_COMPOSE <<'EOF'
**Goal**: Enforce model/GPU placement and add healthchecks/restart policies.

**Acceptance**
- [ ] `ollama-vision` → GPU0 (1080 Ti) only (Qwen2.5‑VL)
- [ ] `ollama-chat`  → GPU1 (1070) only (Hermes3 + Qwen3‑4B)
- [ ] `whisper`, `piper` → GPU1
- [ ] `frigate`, `vision-gateway`, OCR workers → GPU2 (K80)
- [ ] Healthchecks + `restart:on-failure` configured for all
- [ ] Document mapping in `docs/ARCH.md`

**Notes**
Use `NVIDIA_VISIBLE_DEVICES` or Compose `device_requests`.
EOF

create_issue "Compose: GPU pinning & healthchecks" "$BODY_COMPOSE" "type:task,infra:compose,priority:P1"

read -r -d '' BODY_EMBED <<'EOF'
**Goal**: Replace `fake_embed()` with a real embedding model and backfill.

**Tasks**
- [ ] Choose embeddings (SentenceTransformers CPU **or** Ollama embeddings GPU1)
- [ ] Implement in `letta-bridge` (create + search)
- [ ] Migration script to re-embed existing memories
- [ ] Update tests, add benchmarks (latency/quality)

**Acceptance**
- [ ] `/memory/search` returns relevant results on seed dataset
- [ ] Backfill completes; no API downtime
EOF

create_issue "Memory: real embeddings + backfill" "$BODY_EMBED" "type:feat,service:memory,priority:P1,testing"

read -r -d '' BODY_VISION_ROUTER <<'EOF'
**Goal**: Event-driven vision routing with K80 pre/post and HA human-in-the-loop.

**Tasks**
- [ ] K80 preproc: motion/diff, item & anchor proposals, OCR regions
- [ ] Thresholds: `VL_EVENT_THRESH`, cooldowns, dedupe window
- [ ] Qwen2.5-VL on crops only; return normalized schema
- [ ] HA Review Card: Approve/Reject/Edit
- [ ] Entities: `sensor.vision_queue_depth`, etc.

**Acceptance**
- [ ] Showing 8 grocery items → review card → approved → inventory updated
- [ ] No VL call on low-confidence/no-change frames
EOF

create_issue "Vision: Router thresholds + HA review card" "$BODY_VISION_ROUTER" "type:feat,area:vision,priority:P1,integration:ha"

read -r -d '' BODY_CAL_MIRROR <<'EOF'
**Goal**: Mirror work meetings into personal calendar with dedupe & tags.

**Tasks**
- [ ] Source → Sink rules; privacy filters
- [ ] De-dup keys (UID, title+start±delta)
- [ ] SLA: <10 minutes sync
- [ ] Conflict detection + HA notification

**Acceptance**
- [ ] New Teams invite appears in personal calendar within SLA
- [ ] No duplicates across a week of events
EOF

create_issue "Calendar: work→personal mirror + dedupe" "$BODY_CAL_MIRROR" "type:feat,area:planner,priority:P1,integration:ha"

read -r -d '' BODY_NIGHT_CREW <<'EOF'
**Goal**: Nightly consolidation jobs (memory, tasks, menu, coupons) with idempotency.

**Tasks**
- [ ] Compose schedule (cron) for Night Crew services
- [ ] Idempotent job pattern + logging to HA
- [ ] Morning brief generation at 07:30

**Acceptance**
- [ ] EoD check-in → roll-forward plan created
- [ ] Morning brief card shows top 3 and energy-aware schedule
EOF

create_issue "Night Crew: schedules + idempotent jobs" "$BODY_NIGHT_CREW" "type:feat,area:planner,priority:P1"

read -r -d '' BODY_HA_DASH <<'EOF'
**Goal**: HA-first visibility/controls for Inventory, Today, Vision, Night Crew.

**Tasks**
- [ ] Helpers/entities (inventory, switches, selects, sensors)
- [ ] Lovelace dashboards: Inventory, Today, Vision Signals, Night Crew, Health
- [ ] Automations: EoD check-in, Morning brief, Vision approval, Work mirror

**Acceptance**
- [ ] Single HA dashboard surfaces all key controls and signals
EOF

create_issue "HA: dashboards, helpers, automations" "$BODY_HA_DASH" "type:feat,integration:ha,priority:P1,docs"

read -r -d '' BODY_PAPRIKA <<'EOF'
**Goal**: Paprika integration for recipes, pantry sync, grocery lists.

**Tasks**
- [ ] Auth + token storage
- [ ] Periodic sync + conflict rules (HA is source of truth for inventory)
- [ ] Dietician agent hooks (menus, substitutions, budget)

**Acceptance**
- [ ] Weekly menu plan uses pantry-first
- [ ] Grocery list generated with missing items and swaps
EOF

create_issue "Paprika: auth + sync + dietician hooks" "$BODY_PAPRIKA" "type:feat,integration:paprika,priority:P1"

read -r -d '' BODY_PRIVACY <<'EOF'
**Goal**: Privacy modes & consent for camera/screen features.

**Tasks**
- [ ] `switch.privacy_pause`, `switch.vision_on`, `switch.screen_watch_on`
- [ ] Room-level opt-in for emotion detection (off by default)
- [ ] Redaction: crop-to-anchors, mask sensitive regions

**Acceptance**
- [ ] Toggling privacy pause disables captures and VL calls instantly
EOF

create_issue "Privacy: modes, toggles, and redaction" "$BODY_PRIVACY" "type:feat,integration:ha,priority:P1,area:vision"

read -r -d '' BODY_CI <<'EOF'
**Goal**: Basic CI (lint, tests) and container build checks.

**Tasks**
- [ ] GitHub Actions: Python lint/tests; Docker build
- [ ] Cache deps; matrix for services where useful
- [ ] Status badges in README

**Acceptance**
- [ ] CI green on main; required checks for PR merge
EOF

create_issue "CI: lint, tests, container builds" "$BODY_CI" "type:task,testing,priority:P2"

read -r -d '' BODY_BACKUPS <<'EOF'
**Goal**: Backups for Postgres/Redis and restore runbook.

**Tasks**
- [ ] Nightly pg_dump + S3/local rotation
- [ ] Redis snapshotting config
- [ ] `docs/RUNBOOK.md` restore steps

**Acceptance**
- [ ] Test restore on fresh instance succeeds
EOF

create_issue "Ops: backups & restore runbook" "$BODY_BACKUPS" "type:task,priority:P2,docs"

read -r -d '' BODY_LOGS <<'EOF'
**Goal**: Centralized logs and health.

**Tasks**
- [ ] Unified log format; container log levels
- [ ] Health endpoints surfaced in HA (sensors)
- [ ] Optional: Loki + Grafana stack

**Acceptance**
- [ ] HA dashboard shows green/amber/red for all services
EOF

create_issue "Observability: logs & health in HA" "$BODY_LOGS" "type:task,priority:P2,integration:ha"

# ----- Acceptance Test Issues --------------------------------------------

read -r -d '' BODY_AT1 <<'EOF'
**AT‑1 Voice E2E**
Scenario: "Add milk to groceries"
- [ ] STT → intent → Paprika list updated
- [ ] GLaDOS confirms via TTS
- [ ] HA shows updated list
EOF

create_issue "AT‑1: Voice end‑to‑end" "$BODY_AT1" "testing,priority:P1,area:voice,integration:ha"

read -r -d '' BODY_AT2 <<'EOF'
**AT‑2 Grocery Vision**
Scenario: Show 8 items to camera
- [ ] Review card appears
- [ ] Approve → inventory entities + DB updated
- [ ] Reject/Edit works and is persisted
EOF

create_issue "AT‑2: Grocery vision flow" "$BODY_AT2" "testing,priority:P1,area:vision,integration:ha"

read -r -d '' BODY_AT3 <<'EOF'
**AT‑3 Nightly Consolidation**
- [ ] EoD check‑in persists summary
- [ ] Morning brief at 07:30 with energy‑aware plan
- [ ] Roll‑forward tasks with reasons
EOF

create_issue "AT‑3: Nightly consolidation" "$BODY_AT3" "testing,priority:P1,area:planner"

read -r -d '' BODY_AT4 <<'EOF'
**AT‑4 Work Mirror**
- [ ] New Teams/Outlook invite mirrored to personal < 10 min
- [ ] No duplicates across 7 days
- [ ] Conflicts notified in HA
EOF

create_issue "AT‑4: Work→personal calendar mirror" "$BODY_AT4" "testing,priority:P1,area:planner,integration:ha"

read -r -d '' BODY_AT5 <<'EOF'
**AT‑5 PC Automation**
Scenario: "Export Excel to PDF"
- [ ] Steps executed via PyAutoGUI
- [ ] Output verified by screenshot/anchor
- [ ] Errors retried or reported
EOF

create_issue "AT‑5: PC automation flow" "$BODY_AT5" "testing,priority:P2,area:vision"

read -r -d '' BODY_AT6 <<'EOF'
**AT‑6 Dietician Weekly Plan**
- [ ] Pantry‑first menu generated
- [ ] Missing items → grocery list with substitutions
- [ ] HA dashboard card renders plan
EOF

create_issue "AT‑6: Dietician weekly plan" "$BODY_AT6" "testing,priority:P2,integration:paprika"

echo "All issues created for $REPO ✅"
