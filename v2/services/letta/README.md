# Letta Service Skeleton

This directory will host the Letta Dynamic group for v2:

- **Orchestrator (manager)** – enforces S2P → Hermes → Qwen-VL routing policy and owns `ha_call_service`.
- **Hermes** – fast participant (≤512 tokens / ≤2 s) for routine HA queries.
- **Qwen-VL** – heavy/vision participant (1024–2048 tokens / ≤6 s) with Router-driven fallback.
- **Optional** – Memory/archival background agent and HA logger for telemetry writes.

## Planned Layout

```
services/letta/
  config/
    orchestrator.yaml
    hermes.yaml
    qwen_vl.yaml
    dynamic_group.yaml
  prompts/
    orchestrator_prompt.md
    hermes_prompt.md
    qwen_vl_prompt.md
  scripts/
    bootstrap_agents.py  # uses Letta Agents/Groups API
```

- Configs should encode budgets, termination tokens, and shared memory block mounts as described in `docs/ROADMAP.md` (Phase 3).
- Scripts will call Letta Agents API to create/update agents and assemble the Dynamic group.
- Remember to enable step streaming in configs for observability.

Populate these files once the agent generation pipeline is ready.
