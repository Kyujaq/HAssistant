# Inventory
- `sensor.pantry_inventory` - REST snapshot from orchestrator inventory service (schema_version + items + updated_at).
- `input_number.inv_milk_qty`, `input_number.inv_eggs_qty`, `input_number.inv_bread_qty` - top-item helpers for quick adjustments.
- `button.inventory_sync_from_json` - template button calling `rest_command.inventory_sync_from_json` to push HA state back to orchestrator.

# Today
- `select.energy_band` - template select posting desired energy band to orchestrator `/config`.
- `select.focus_mode` - template select for routing focus (deep/admin/errands).
- `sensor.last_orchestrator_reply` - REST sensor reading the latest orchestrator reply for automations.
- `switch.privacy_pause` - REST switch toggling orchestrator privacy halt.

# Vision Signals
- `sensor.vl_requests_today` - Prometheus scrape of VL text hits (orchestrator metrics).
- `sensor.vision_events_ingested` - Prometheus scrape of vision ingest counter.
- `sensor.vision_router_queue_depth` - REST sensor hitting `http://vision-router:8050/stats` (queue depth, attributes include lock, totals, GPU list).
- `sensor.vision_router_lock_enabled`, `sensor.vision_router_events_total`, `sensor.vision_router_escalations_total` - template sensors bound to the `/stats` attributes for dashboards and alerts.
- `sensor.vision_router_gpu0_util_percent`, `sensor.vision_router_gpu0_mem_free_gb` - NVML telemetry (utilisation + free memory) surfaced from the new `/stats` endpoint.
- `switch.vision_on`, `switch.screen_watch_on` - REST switches posting to `http://vision-router:8050/config` to gate processing/escalations.

# Night Crew
- `sensor.pantry_inventory` + top input_numbers reused for nightly runs.
- `calendar.menu_plan`, `calendar.personal`, `calendar.work_mirror` - leverage existing HA calendars for shift planning.
- Automations in `automations_core.yaml` emit notifications for EOD check-in, morning brief, vision->inventory review, and work mirror.

# System Health
- `sensor.orchestrator_config` - live view of pause/mode state via `/config`.
- `sensor.orchestrator_privacy_paused_total` - counter of chat requests blocked by privacy pause.
- `sensor.orchestrator_memory_pre_avg_ms` / `sensor.orchestrator_memory_pre_slow_count` - latency guardrails derived from Prometheus histogram.
- `sensor.orchestrator_context_characters_sum` - monitors prompt growth; ideal for simple trending cards.
- `sensor.vision_router_queue_depth`, `sensor.vision_router_gpu0_util_percent`, `sensor.vision_router_gpu0_mem_free_gb` - surfaced on the System Health view so the HA sidebar shows queue pressure and GPU availability at a glance.
