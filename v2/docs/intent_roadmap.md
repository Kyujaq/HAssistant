# GLaDOS Assistant — Intent Spec v0.2 (Annotate Me)

> Annotate anywhere you see **My notes / intent:**. We’ll turn this into issues/PRs after your pass.

## 0) North Star

* **Persona:** GLaDOS-style personal assistant (witty, dry, supportive; no meanness IRL).
  **My notes / intent:** [ ]
* **Scope:** Organize personal + work life; remember context; plan, re-plan, and act; see via cameras and a screen-capture dongle; use tools and automations; everything visible/controllable in Home Assistant (HA).
  **My notes / intent:** [ ]
* **Architecture bias:** Local-first micro-services; **CrewAI** to orchestrate crews; **Qwen Agent** for agent runtimes; **HA** as the central control plane + UX (dashboards, entities).
  **My notes / intent:** [ ]

---

## 1) Definitive Model & GPU Assignment (v0.2)

| Role                        | Model                               | GPU                  | Notes                                                                                       |
| --------------------------- | ----------------------------------- | -------------------- | ------------------------------------------------------------------------------------------- |
| **Vision LLM (multimodal)** | **Qwen 2.5 VL**                     | **1080 Ti (GPU0)**   | Only invoked on-demand (event-triggered) after K80 preprocessing.                           |
| **Persona / Chat**          | **Hermes 3 (3B)**                   | **GTX 1070 (GPU1)**  | Fast, GLaDOS voice; handles day-to-day banter, confirmations, short answers.                |
| **Reasoning / “Thinker”**   | **Qwen3 4B**                        | **GTX 1070 (GPU1)**  | Tool-aware chain-of-thought *internally*, plans, routing hints.                             |
| **Vision Pre/Post**         | **Classical CV + lightweight nets** | **Tesla K80 (GPU2)** | Motion, diffing, crops, OCR pre/post, queueing; **decides when** Qwen2.5-VL must be called. |

**Enforcement notes**

* Pin containers with `device_requests` or `NVIDIA_VISIBLE_DEVICES`, e.g. `ollama-chat -> GPU1`, `ollama-vision -> GPU0`, `frigate/vision-gateway -> GPU2`.
* Make VL calls **edge-triggered**: K80 preprocess emits events `(crop, kind, confidence)` → Vision Router → VL only if confidence/novelty threshold met.
  **My notes / intent:** [ ]

---

## 2) HA-Centric Control & Visibility

Everything should be surfaced and controllable through **Home Assistant** in addition to the assistant’s voice/UI.

### 2.1 HA Entities & Dashboards

* **Inventory**: each item either as (a) HA **entity per item** with attributes, or (b) a single **JSON attribute** on `sensor.pantry_inventory`.
  *Recommended*: hybrid → top-50 items (entities) + master JSON sensor for long tail.
  **My notes / intent:** [ ]
* **Queues**: `sensor.vision_queue_depth`, `sensor.vl_requests_today`, `sensor.memory_additions_today`.
* **Switches**: `switch.privacy_pause`, `switch.vision_on`, `switch.screen_watch_on`.
* **Selects**: `select.energy_band` (low / medium / high), `select.focus_mode` (deep / admin / errands).
* **Calendars**: `calendar.work_mirror`, `calendar.personal`, `calendar.menu_plan`.
* **Dashboards**: *Inventory*, *Today*, *Night Crew*, *Vision Signals*, *System Health*.

**My notes / intent:** [ ]

### 2.2 HA Automations

* **End-of-day check‑in**: trigger at configurable time → prompt assistant → record accomplished/blocked → reschedule.
* **Morning brief**: 07:30 → energy band check + day plan + top 3 must-dos.
* **Vision to Inventory**: grocery event → review card in HA → user Approve/Reject → DB + entities updated.
* **Work mirror**: new work event → mirror to personal (with tags) → notify if collision.

**My notes / intent:** [ ]

---

## 3) Vision Pipeline (Event-Driven)

> **Status update (Oct 2025):** The K80 vision stack now runs on the dedicated VM.
> Local `v2/docker-compose.yml` keeps a commented profile stub; enable it only when
> the remote gateway returns to on-prem.

1. **Capture Sources**: webcams, HDMI screen-capture dongle.
2. **K80 Preprocess** (GPU2):

   * Motion/novelty detection, frame differencing.
   * Object proposals (groceries, UI anchors), OCR region proposals.
   * Emotion/activity *optional* (off by default; room-level opt-in).
3. **Decision Gate**: if `(class != known || qty change || anchor hit)` and confidence ≥ threshold → enqueue **VL call**.
4. **VL (GPU0)**: Qwen2.5-VL runs on cropped regions; returns structured schema.
5. **Postprocess (K80)**: normalize → dedupe → upsert inventory/task/cue; emit HA events and review-card.
6. **Human-in-the-loop**: HA card “Approve/Reject/Edit quantities/labels”.

**My notes / intent:** [ ]

**Inventory schema** (HA+DB):

```json
{
  "name": "Greek yogurt",
  "brand": "Oikos",
  "size": 750,
  "unit": "g",
  "qty": 1,
  "location": "fridge",
  "acquired_at": "2025-10-13",
  "expiry": "2025-10-20",
  "source": "camera",
  "confidence": 0.92
}
```

**My notes / intent:** [ ]

---

## 4) Crews & Responsibilities

### 4.1 Orchestrator (CrewAI Director)

* Routes intents to crews; enforces HA-first visibility; logs all tool calls to HA `assist_history`. **My notes / intent:** [ ]

### 4.2 Day Crew

* **Planner**: calendar math, energy-aware scheduling, reschedules after check-ins.
* **Calendar**: syncs work→personal mirror; de-dup + tagging; SLA 10 min.
* **Tasks**: maintain unified backlog; chunk into calendar blocks. **My notes / intent:** [ ]

### 4.3 Vision Crew

* **Grocery Vision**: camera → inventory (approval loop).
* **Screen Vision**: anchored OCR on Outlook/Teams; detect invites, status, output files.
* **Context Agent (optional)**: posture/facial cues → suggestions; strict opt-in. **My notes / intent:** [ ]

### 4.4 Kitchen Crew

* **Paprika Agent**: sync recipes/lists.
* **Dietician Agent**: menus; pantry-first; coupons; constraints.
* **Inventory Agent**: expiry tracking; “use‑soon” nudges; weekly audit. **My notes / intent:** [ ]

### 4.5 Night Crew (scheduled)

* Consolidate memory; fill blanks; summarize the day.
* Reconcile tasks vs actuals; roll-forward plan; prep morning brief.
* Scan flyers/deals; propose grocery swaps; update menu & list. **My notes / intent:** [ ]

### 4.6 Workstation Crew

* **PC Control**: PyAutoGUI + Tesseract; verify by screenshot.
* **Windows Voice Bridge**: TTS → laptop assistant; command sanitation. **My notes / intent:** [ ]

---

## 5) Concrete Changes to the Repo/Compose

### 5.1 Docker Compose (GPU pinning)

* `ollama-vision` → `NVIDIA_VISIBLE_DEVICES=0` (1080 Ti)
* `ollama-chat`  → `NVIDIA_VISIBLE_DEVICES=1` (1070)
* `whisper` / `piper` → `NVIDIA_VISIBLE_DEVICES=1` (1070)
* `frigate`, `vision-gateway`, OCR workers → `NVIDIA_VISIBLE_DEVICES=2` (K80)
* Add healthchecks per service; restart policies `on-failure:3`. **My notes / intent:** [ ]

### 5.2 Env / Configuration

* `.env`: `GPU_MAP=vision:0,chat:1,stt:1,tts:1,preproc:2`
* `.env`: `VL_EVENT_THRESH=0.72`, `VL_COOLDOWN_S=15`, `VISION_QUEUE_MAX=64`
* `.env`: `EMOTION_DETECT=off` (default); per-room override. **My notes / intent:** [ ]

### 5.3 Models

* Ensure `Modelfile.hermes3` (chat), `Modelfile.qwen3_4b` (reason), `Modelfile.qwen2_5_vl` (vision).
* Load with `ollama create` on the correct host; verify `ollama list`. **My notes / intent:** [ ]

### 5.4 HA Integration

* Create HA Helpers/Entities per §2.1.
* Add Lovelace dashboards: *Inventory*, *Today*, *Vision Signals*, *Night Crew*.
* Build HA automations for EoD check‑in, morning brief, work-mirror, vision-approval. **My notes / intent:** [ ]

### 5.5 Memory Embeddings

* Replace `fake_embed()` with `sentence-transformers` (CPU OK) or Ollama embeddings (GPU1) + pgvector.
* Add backfill job to re-embed existing memories. **My notes / intent:** [ ]

---

## 6) Acceptance Tests (v0.2)

1. **Voice E2E**: “Add milk to groceries” → HA grocery list updated; GLaDOS confirms.
   **My notes / intent:** [ ]
2. **Grocery Vision**: show 8 items → HA review card → approve → inventory entities + DB updated.
   **My notes / intent:** [ ]
3. **Nightly Consolidation**: EoD check‑in triggers roll‑forward; morning brief at 07:30 with energy‑aware plan.
   **My notes / intent:** [ ]
4. **Work Mirror**: Teams invite detected on screen → mirrored to personal within 10 min; no duplicates.
   **My notes / intent:** [ ]
5. **PC Automation**: “Export Excel to PDF” completes; file verified by screen readback.
   **My notes / intent:** [ ]
6. **Dietician Plan**: weekly menu uses pantry first; gaps → grocery list with substitutions.
   **My notes / intent:** [ ]

---

## 7) Privacy & Safety

* **Modes**: privacy pause; work-only; home-only; per-source toggles.
* **Redaction**: crop to anchors; mask sensitive regions; avoid full-screen dumps.
* **Consent**: camera-based emotion detection opt-in, per-room. **My notes / intent:** [ ]

---

## 8) Roadmap (turn into Issues)

*

**My notes / intent:** [ ]

---

## 9) Satellite & Mobile Interfaces

### 9.1 Raspberry Pi Satellite Node

* **Purpose:** always‑on local mic array for wake‑word detection and STT streaming to HA Assist.
* **Wake‑word engine:** Porcupine (default model `computer` or custom `.ppn`).
* **Audio path:** mic → Porcupine → Wyoming Whisper STT → HA Assist intent.
* **Outbound:** small OLED/LED ring optional for status feedback.
* **Runtime:** `clients/pi_client.py` (or `pi_client_usb_audio.py` for external dongle).
* **Configuration:** environment file `pi_client.env` includes `PV_ACCESS_KEY`, `ASSIST_URL`, `MQTT_BROKER`, and device ID.
* **HA Integration:** exposes sensors `binary_sensor.pi_satellite_active`, `sensor.last_wakeword`, and events `wakeword_detected`.
* **Networking:** connect via Tailscale/VPN; must resolve `assistant-brain.assistant_default`.
* **Optional expansions:** temperature, proximity, or small display for status.

**My notes / intent:** [ ]

### 9.2 HA Mobile App Client

* **Purpose:** voice interface when away from home; secondary mic and display for GLaDOS responses.
* **Trigger:** long‑press HA Assist mic or dedicated dashboard button → sends voice to same Assist endpoint as Pi.
* **Display:** shows text replies, TTS playback through device speaker.
* **Push events:** receives notifications for: `morning_brief_ready`, `task_due`, `meeting_soon`, `inventory_low`.
* **Security:** token‑scoped mobile account; TLS via Nabu Casa or VPN.
* **Optional:** location sensor feeds energy/availability context (e.g., “on commute”, “at work”).

**My notes / intent:** [ ]

---

## Step 1 — Streaming Speech Stack (Claude Code prompt)

> **Goal:** Keep Wyoming at the edges for HA/Pi, but enable **streaming** and **GPU STT** by routing through a local **wyoming_openai** proxy to **Speaches** (faster‑whisper + Piper/Kokoro). Keep native `wyoming-piper` alongside for A/B testing.

**You are DevOps for HAssistant v2. Produce the following artifacts ready to paste into the repo.**

### A) `v2/docker-compose.yml` (full file)

**Requirements**

* `name: hassistant_v2`
* Services:

  1. **ollama-chat** (GPU1) — expose 11434; healthcheck `/api/tags`. (We’ll load Hermes3 + Qwen3‑4B.)
  2. **wyoming_openai** — listens on **TCP 10300 (STT)** and **TCP 10200 (TTS)** for HA; forwards to Speaches endpoints.
  3. **speaches** (GPU1) — OpenAI‑compatible server providing:

     * STT: `POST /v1/audio/transcriptions` (faster‑whisper, CUDA)
     * TTS: `POST /v1/audio/speech` (Piper/Kokoro)
       Expose the HTTP port and add a `/health` endpoint healthcheck.
  4. **wyoming-piper** (GPU1) — native fallback/A‑B for streaming TTS.
* **GPU pinning**: all the above should run on **GPU1** (`NVIDIA_VISIBLE_DEVICES=1` or `device_requests`).
* **Healthchecks** for every container; `restart: on-failure:3`.
* **Networks**: default is fine (Compose will create `hassistant_v2_default`).

**wyoming_openai → Speaches mapping (use environment vars):**

```
ASR_URL=http://speaches:PORT/v1/audio/transcriptions
TTS_URL=http://speaches:PORT/v1/audio/speech
# Optional fallbacks
FALLBACK_TTS_HOST=wyoming-piper
FALLBACK_TTS_PORT=10200
```

*(Replace `PORT` with the actual Speaches container port per its image/README.)*

### B) `v2/scripts/model_load.sh`

* Pull/create **Hermes3** and **Qwen3‑4B** into `ollama-chat` and print `ollama list`.

### C) Tests

1. `v2/tests/smoke_ollama_chat.sh` — curl `/api/tags` OK.
2. `v2/tests/smoke_proxy_routes.sh` —

   * Hit **wyoming_openai** STT/TTS health (TCP check or HTTP if available).
   * Curl **Speaches** `/health` returns 200.
3. `v2/tests/latency_streaming.md` — instructions to verify streaming TTS and GPU STT:

   * **Streaming TTS**: send a long paragraph via HA Assist; confirm audio starts <500ms and continues chunked.
   * **GPU STT**: run `watch -n1 nvidia-smi` during speech and record utilization vs CPU baseline.

### D) Output format

Return **the full Compose YAML** and **the three files** exactly as code blocks ready to paste.

### E) Compose guidance / notes for you to follow

* Choose official images if available; otherwise, define `build` contexts from the upstream repos. Document the chosen image + port in comments.
* Enable **CUDA** in Speaches (faster‑whisper GPU). If an env flag is required (e.g., `CUDA_VISIBLE_DEVICES=1` or `USE_CUDA=1`), set it and add a note.
* For `wyoming_openai`, ensure it binds both TTS (10200) and STT (10300) Wyoming endpoints and forwards to Speaches’ OpenAI routes.
* Keep **wyoming-piper** reachable at 10200 as a fallback (A/B). If conflicts, expose proxy TTS on 10210 and wire HA accordingly; note the chosen ports in a header comment at the top of the file.
* All services must have clear **healthchecks**; fail fast if backends are unreachable.

---

---

## Appendix: GitHub Issues — Auto‑Create Script (gh CLI)

> Run this locally to open all the issues in `Kyujaq/HAssistant`. Review/edit titles & text before running.
>
> **Prereqs**
>
> 1. Install GitHub CLI: [https://cli.github.com/](https://cli.github.com/)
> 2. Authenticate once: `gh auth login`
> 3. `cd` to any folder (doesn’t have to be the repo)
>
> **Usage**
>
> ```bash
> bash create_hasstant_issues.sh
> ```
>
> This will:
>
> * Create labels (idempotent; ignores if they exist)
> * Create ~20 scoped issues with checklists and acceptance criteria
>
> ```bash
> #!/usr/bin/env bash
> set -euo pipefail
>
> REPO="Kyujaq/HAssistant"   # change if you fork
>
> # --- Labels ---------------------------------------------------------------
> declare -A LABELS=(
>   ["type:feat"]="#1E90FF"
>   ["type:task"]="#A9A9A9"
>   ["type:bug"]="#DC143C"
>   ["priority:P1"]="#FF4500"
>   ["priority:P2"]="#FFA500"
>   ["priority:P3"]="#32CD32"
>   ["area:vision"]="#5F9EA0"
>   ["area:voice"]="#9370DB"
>   ["area:planner"]="#2E8B57"
>   ["service:memory"]="#20B2AA"
>   ["service:orchestrator"]="#00CED1"
>   ["integration:ha"]="#228B22"
>   ["integration:paprika"]="#8B4513"
>   ["infra:compose"]="#708090"
>   ["docs"]="#000000"
>   ["testing"]="#696969"
> )
>
> echo "Creating labels (idempotent)…"
> for name in "${!LABELS[@]}"; do
>   color=${LABELS[$name]#\#}
>   gh label create "$name" --color "$color" --repo "$REPO" 2>/dev/null || true
> done
>
> create_issue() {
>   local title="$1"; shift
>   local body="$1"; shift
>   local labels="$1"; shift
>   gh issue create --repo "$REPO" --title "$title" --body "$body" --label $labels
> }
>
> # --- Issues ---------------------------------------------------------------
>
> read -r -d '' BODY_COMPOSE <<'EOF'
> **Goal**: Enforce model/GPU placement and add healthchecks/restart policies.
>
> **Acceptance**
> - [ ] `ollama-vision` → GPU0 (1080 Ti) only (Qwen2.5‑VL)
> - [ ] `ollama-chat`  → GPU1 (1070) only (Hermes3 + Qwen3‑4B)
> - [ ] `whisper`, `piper` → GPU1
> - [ ] `frigate`, `vision-gateway`, OCR workers → GPU2 (K80)
> - [ ] Healthchecks + `restart:on-failure` configured for all
> - [ ] Document mapping in `docs/ARCH.md`
>
> **Notes**
> Use `NVIDIA_VISIBLE_DEVICES` or Compose `device_requests`.
> EOF
>
> create_issue "Compose: GPU pinning & healthchecks" "$BODY_COMPOSE" "type:task,infra:compose,priority:P1"
>
> read -r -d '' BODY_EMBED <<'EOF'
> **Goal**: Replace `fake_embed()` with a real embedding model and backfill.
>
> **Tasks**
> - [ ] Choose embeddings (SentenceTransformers CPU **or** Ollama embeddings GPU1)
> - [ ] Implement in `letta-bridge` (create + search)
> - [ ] Migration script to re-embed existing memories
> - [ ] Update tests, add benchmarks (latency/quality)
>
> **Acceptance**
> - [ ] `/memory/search` returns relevant results on seed dataset
> - [ ] Backfill completes; no API downtime
> EOF
>
> create_issue "Memory: real embeddings + backfill" "$BODY_EMBED" "type:feat,service:memory,priority:P1,testing"
>
> read -r -d '' BODY_VISION_ROUTER <<'EOF'
> **Goal**: Event-driven vision routing with K80 pre/post and HA human-in-the-loop.
>
> **Tasks**
> - [ ] K80 preproc: motion/diff, item & anchor proposals, OCR regions
> - [ ] Thresholds: `VL_EVENT_THRESH`, cooldowns, dedupe window
> - [ ] Qwen2.5-VL on crops only; return normalized schema
> - [ ] HA Review Card: Approve/Reject/Edit
> - [ ] Entities: `sensor.vision_queue_depth`, etc.
>
> **Acceptance**
> - [ ] Showing 8 grocery items → review card → approved → inventory updated
> - [ ] No VL call on low-confidence/no-change frames
> EOF
>
> create_issue "Vision: Router thresholds + HA review card" "$BODY_VISION_ROUTER" "type:feat,area:vision,priority:P1,integration:ha"
>
> read -r -d '' BODY_CAL_MIRROR <<'EOF'
> **Goal**: Mirror work meetings into personal calendar with dedupe & tags.
>
> **Tasks**
> - [ ] Source → Sink rules; privacy filters
> - [ ] De-dup keys (UID, title+start±delta)
> - [ ] SLA: <10 minutes sync
> - [ ] Conflict detection + HA notification
>
> **Acceptance**
> - [ ] New Teams invite appears in personal calendar within SLA
> - [ ] No duplicates across a week of events
> EOF
>
> create_issue "Calendar: work→personal mirror + dedupe" "$BODY_CAL_MIRROR" "type:feat,area:planner,priority:P1,integration:ha"
>
> read -r -d '' BODY_NIGHT_CREW <<'EOF'
> **Goal**: Nightly consolidation jobs (memory, tasks, menu, coupons) with idempotency.
>
> **Tasks**
> - [ ] Compose schedule (cron) for Night Crew services
> - [ ] Idempotent job pattern + logging to HA
> - [ ] Morning brief generation at 07:30
>
> **Acceptance**
> - [ ] EoD check-in → roll-forward plan created
> - [ ] Morning brief card shows top 3 and energy-aware schedule
> EOF
>
> create_issue "Night Crew: schedules + idempotent jobs" "$BODY_NIGHT_CREW" "type:feat,area:planner,priority:P1"
>
> read -r -d '' BODY_HA_DASH <<'EOF'
> **Goal**: HA-first visibility/controls for Inventory, Today, Vision, Night Crew.
>
> **Tasks**
> - [ ] Helpers/entities (inventory, switches, selects, sensors)
> - [ ] Lovelace dashboards: Inventory, Today, Vision Signals, Night Crew, Health
> - [ ] Automations: EoD check-in, Morning brief, Vision approval, Work mirror
>
> **Acceptance**
> - [ ] Single HA dashboard surfaces all key controls and signals
> EOF
>
> create_issue "HA: dashboards, helpers, automations" "$BODY_HA_DASH" "type:feat,integration:ha,priority:P1,docs"
>
> read -r -d '' BODY_PAPRIKA <<'EOF'
> **Goal**: Paprika integration for recipes, pantry sync, grocery lists.
>
> **Tasks**
> - [ ] Auth + token storage
> - [ ] Periodic sync + conflict rules (HA is source of truth for inventory)
> - [ ] Dietician agent hooks (menus, substitutions, budget)
>
> **Acceptance**
> - [ ] Weekly menu plan uses pantry-first
> - [ ] Grocery list generated with missing items and swaps
> EOF
>
> create_issue "Paprika: auth + sync + dietician hooks" "$BODY_PAPRIKA" "type:feat,integration:paprika,priority:P1"
>
> read -r -d '' BODY_PRIVACY <<'EOF'
> **Goal**: Privacy modes & consent for camera/screen features.
>
> **Tasks**
> - [ ] `switch.privacy_pause`, `switch.vision_on`, `switch.screen_watch_on`
> - [ ] Room-level opt-in for emotion detection (off by default)
> - [ ] Redaction: crop-to-anchors, mask sensitive regions
>
> **Acceptance**
> - [ ] Toggling privacy pause disables captures and VL calls instantly
> EOF
>
> create_issue "Privacy: modes, toggles, and redaction" "$BODY_PRIVACY" "type:feat,integration:ha,priority:P1,area:vision"
>
> read -r -d '' BODY_CI <<'EOF'
> **Goal**: Basic CI (lint, tests) and container build checks.
>
> **Tasks**
> - [ ] GitHub Actions: Python lint/tests; Docker build
> - [ ] Cache deps; matrix for services where useful
> - [ ] Status badges in README
>
> **Acceptance**
> - [ ] CI green on main; required checks for PR merge
> EOF
>
> create_issue "CI: lint, tests, container builds" "$BODY_CI" "type:task,testing,priority:P2"
>
> read -r -d '' BODY_BACKUPS <<'EOF'
> **Goal**: Backups for Postgres/Redis and restore runbook.
>
> **Tasks**
> - [ ] Nightly pg_dump + S3/local rotation
> - [ ] Redis snapshotting config
> - [ ] `docs/RUNBOOK.md` restore steps
>
> **Acceptance**
> - [ ] Test restore on fresh instance succeeds
> EOF
>
> create_issue "Ops: backups & restore runbook" "$BODY_BACKUPS" "type:task,priority:P2,docs"
>
> read -r -d '' BODY_LOGS <<'EOF'
> **Goal**: Centralized logs and health.
>
> **Tasks**
> - [ ] Unified log format; container log levels
> - [ ] Health endpoints surfaced in HA (sensors)
> - [ ] Optional: Loki + Grafana stack
>
> **Acceptance**
> - [ ] HA dashboard shows green/amber/red for all services
> EOF
>
> create_issue "Observability: logs & health in HA" "$BODY_LOGS" "type:task,priority:P2,integration:ha"
>
> # ----- Acceptance Test Issues --------------------------------------------
>
> read -r -d '' BODY_AT1 <<'EOF'
> **AT‑1 Voice E2E**
> Scenario: "Add milk to groceries"
> - [ ] STT → intent → Paprika list updated
> - [ ] GLaDOS confirms via TTS
> - [ ] HA shows updated list
> EOF
>
> create_issue "AT‑1: Voice end‑to‑end" "$BODY_AT1" "testing,priority:P1,area:voice,integration:ha"
>
> read -r -d '' BODY_AT2 <<'EOF'
> **AT‑2 Grocery Vision**
> Scenario: Show 8 items to camera
> - [ ] Review card appears
> - [ ] Approve → inventory entities + DB updated
> - [ ] Reject/Edit works and is persisted
> EOF
>
> create_issue "AT‑2: Grocery vision flow" "$BODY_AT2" "testing,priority:P1,area:vision,integration:ha"
>
> read -r -d '' BODY_AT3 <<'EOF'
> **AT‑3 Nightly Consolidation**
> - [ ] EoD check‑in persists summary
> - [ ] Morning brief at 07:30 with energy‑aware plan
> - [ ] Roll‑forward tasks with reasons
> EOF
>
> create_issue "AT‑3: Nightly consolidation" "$BODY_AT3" "testing,priority:P1,area:planner"
>
> read -r -d '' BODY_AT4 <<'EOF'
> **AT‑4 Work Mirror**
> - [ ] New Teams/Outlook invite mirrored to personal < 10 min
> - [ ] No duplicates across 7 days
> - [ ] Conflicts notified in HA
> EOF
>
> create_issue "AT‑4: Work→personal calendar mirror" "$BODY_AT4" "testing,priority:P1,area:planner,integration:ha"
>
> read -r -d '' BODY_AT5 <<'EOF'
> **AT‑5 PC Automation**
> Scenario: "Export Excel to PDF"
> - [ ] Steps executed via PyAutoGUI
> - [ ] Output verified by screenshot/anchor
> - [ ] Errors retried or reported
> EOF
>
> create_issue "AT‑5: PC automation flow" "$BODY_AT5" "testing,priority:P2,area:vision"
>
> read -r -d '' BODY_AT6 <<'EOF'
> **AT‑6 Dietician Weekly Plan**
> - [ ] Pantry‑first menu generated
> - [ ] Missing items → grocery list with substitutions
> - [ ] HA dashboard card renders plan
> EOF
>
> create_issue "AT‑6: Dietician weekly plan" "$BODY_AT6" "testing,priority:P2,integration:paprika"
>
> echo "All issues created for $REPO ✅"
> ```
