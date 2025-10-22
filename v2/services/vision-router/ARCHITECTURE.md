# Vision Router - Architecture & Data Flow

## System Context

```
┌──────────────────────────────────────────────────────────────────────┐
│                           K80 VM Stack                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────┐              ┌──────────────────┐               │
│  │ vision-gateway  │              │ realworld-gateway │               │
│  │ (K80 GPU #0)    │              │ (K80 GPU #1)     │               │
│  ├─────────────────┤              ├──────────────────┤               │
│  │ Screen OCR      │              │ Face/Pose detect │               │
│  │ Slide detect    │              │ Motion analysis  │               │
│  │ Diagram OCR     │              │ Novelty scoring  │               │
│  └────────┬────────┘              └────────┬─────────┘               │
│           │                                │                          │
│           └────────────┬───────────────────┘                          │
│                        │                                              │
│                        ▼                                              │
│              ┌──────────────────┐                                     │
│              │  vision-router   │ ◄─── /events (from gateways)       │
│              │  (CPU service)   │ ◄─── /analyze (from HA)            │
│              ├──────────────────┤                                     │
│              │ • Scoring        │                                     │
│              │ • Pre-filtering  │                                     │
│              │ • GPU monitoring │                                     │
│              │ • Backpressure   │                                     │
│              └────────┬─────────┘                                     │
│                       │                                               │
└───────────────────────┼───────────────────────────────────────────────┘
                        │
                        │ (if score >= threshold)
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Main Host Stack                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                    Orchestrator (8020)                       │     │
│  ├─────────────────────────────────────────────────────────────┤     │
│  │ POST /vision/event (pre)  ─► Memory DB                      │     │
│  │ POST /vision/vl_summarize ─► ollama-vl (1080 Ti)            │     │
│  │ POST /vision/event (post) ─► Memory DB (with VL captions)   │     │
│  └─────────────┬───────────────────────────────────────────────┘     │
│                │                                                      │
│                ▼                                                      │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                  ollama-vl (1080 Ti)                         │     │
│  ├─────────────────────────────────────────────────────────────┤     │
│  │ Model: qwen-vl:8b                                            │     │
│  │ Task: Image captioning, OCR understanding, context           │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Home Assistant (8123)                              │
├──────────────────────────────────────────────────────────────────────┤
│  • Switches: vision_on, screen_watch_on, escalate_vl                 │
│  • Sensors: queue_depth, gpu_util, threshold                         │
│  • Automations: backpressure alerts, ad-hoc analysis                 │
│  • UI: Vision Signals dashboard, Memory timeline                     │
└──────────────────────────────────────────────────────────────────────┘
```

## Vision Router Internal Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      POST /events (from gateways)                    │
│                      POST /analyze (from HA)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Check vision_on flag │
                  └──────────┬───────────┘
                             │
                ┌────────────┴────────────┐
                │ NO                      │ YES
                ▼                         ▼
         ┌─────────────┐         ┌────────────────┐
         │ Skip, log,  │         │ Score via      │
         │ return ID   │         │ scoring.py     │
         └─────────────┘         └────────┬───────┘
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │ score >= threshold?  │
                                └──────────┬───────────┘
                                           │
                             ┌─────────────┴─────────────┐
                             │ NO                        │ YES
                             ▼                           ▼
                  ┌─────────────────┐         ┌─────────────────────┐
                  │ POST pre-summary│         │ _check_backpressure │
                  │ to orchestrator │         │ (auto-adjust thresh)│
                  │ (stage: "pre")  │         └──────────┬──────────┘
                  │ vl: null        │                    │
                  └─────────────────┘                    ▼
                                              ┌─────────────────────┐
                                              │ Acquire lock (opt)  │
                                              │ pending_jobs++      │
                                              └──────────┬──────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────────┐
                                              │ _build_vl_bundle    │
                                              │ (top max_frames +   │
                                              │  OCR text hints)    │
                                              └──────────┬──────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────────┐
                                              │ POST to VL_GATEWAY  │
                                              │ /vision/vl_summarize│
                                              │ (timeout: 60s)      │
                                              └──────────┬──────────┘
                                                         │
                                           ┌─────────────┴─────────────┐
                                           │ Success                   │ Error
                                           ▼                           ▼
                                ┌─────────────────┐         ┌─────────────────┐
                                │ VL result with  │         │ VL_FAILOVER_    │
                                │ summary/captions│         │ TOTAL.inc()     │
                                │ ESC_LAT metric  │         │ return {error}  │
                                └────────┬────────┘         └────────┬────────┘
                                         │                           │
                                         └─────────┬─────────────────┘
                                                   │
                                                   ▼
                                        ┌─────────────────────┐
                                        │ POST post-summary   │
                                        │ to orchestrator     │
                                        │ (stage: "post")     │
                                        │ vl: {...}           │
                                        └──────────┬──────────┘
                                                   │
                                                   ▼
                                        ┌─────────────────────┐
                                        │ Release lock (opt)  │
                                        │ pending_jobs--      │
                                        └──────────┬──────────┘
                                                   │
                                                   ▼
                                        ┌─────────────────────┐
                                        │ Return response     │
                                        │ {id, score,         │
                                        │  escalated: bool}   │
                                        └─────────────────────┘
```

## Backpressure Logic

```
┌──────────────────────────────────────────────────────────────────┐
│             _check_backpressure() - called before escalation     │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
               ┌──────────────────────┐
               │ Now - last_adjusted  │
               │     < 30s?           │
               └──────────┬───────────┘
                          │
            ┌─────────────┴─────────────┐
            │ YES (skip)                │ NO (check)
            ▼                           ▼
     ┌─────────────┐         ┌──────────────────────┐
     │ Return      │         │ Check queue_depth    │
     │ (no change) │         │     > 5?             │
     └─────────────┘         └──────────┬───────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          │ YES                       │ NO
                          ▼                           ▼
               ┌──────────────────────┐    ┌──────────────────────┐
               │ Raise threshold      │    │ Check GPU util       │
               │ +0.1 (cap at 0.85)   │    │ avg >85% for 60s?    │
               │ Log warning          │    └──────────┬───────────┘
               │ Update metrics       │               │
               └──────────────────────┘    ┌──────────┴──────────┐
                                           │ YES                 │ NO
                                           ▼                     ▼
                                ┌──────────────────────┐  ┌─────────────┐
                                │ Raise threshold      │  │ Return      │
                                │ +0.1 (cap at 0.85)   │  │ (no change) │
                                │ Log warning          │  └─────────────┘
                                │ Update metrics       │
                                └──────────────────────┘
```

## GPU Monitoring Background Task

```
┌──────────────────────────────────────────────────────────────────┐
│              _gpu_poller_task() - started at app startup         │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ While True:   │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ sleep(5.0)    │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────────────┐
                  │ snapshot_gpus()       │
                  │ (via common module)   │
                  └───────┬───────────────┘
                          │
                          ▼
                  ┌───────────────────────┐
                  │ Calculate avg_util    │
                  │ across all GPUs       │
                  └───────┬───────────────┘
                          │
                          ▼
                  ┌───────────────────────┐
                  │ _gpu_util_history     │
                  │ .append(avg_util)     │
                  │ (deque, maxlen=12)    │
                  └───────┬───────────────┘
                          │
                          ▼
                  ┌───────────────────────┐
                  │ Update _gpu_cache     │
                  │ (gpus, last_update)   │
                  └───────┬───────────────┘
                          │
                          ▼
                  ┌───────────────────────┐
                  │ Update Prometheus     │
                  │ gauges (util, mem)    │
                  └───────┬───────────────┘
                          │
                          ▼
                  ┌───────────────────────┐
                  │ Catch exceptions,     │
                  │ log, continue loop    │
                  └───────────────────────┘
```

## Configuration Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    Environment Variables                          │
│  (ORCHESTRATOR_URL, VISION_ESCALATE_VL, THRESHOLD, etc.)         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ config dict          │
              │ (module-level state) │
              └──────────┬───────────┘
                         │
         ┌───────────────┼───────────────┐
         │ GET /config   │ POST /config  │
         ▼               ▼               ▼
  ┌─────────────┐ ┌─────────────────┐  ┌──────────────────┐
  │ Return      │ │ Update config   │  │ HA Switches      │
  │ current     │ │ dict            │  │ call POST /config│
  │ config JSON │ │ Call            │  │ to change runtime│
  │             │ │ _update_config_ │  │ settings         │
  └─────────────┘ │ metrics()       │  └──────────────────┘
                  │ Return new      │
                  │ config JSON     │
                  └─────────┬───────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │ Prometheus      │
                  │ vision_config_  │
                  │ state{key}      │
                  └─────────────────┘
```

## Metrics & Observability

### Prometheus Metrics Hierarchy

```
vision_*
├── events_total{source}           [Counter]
├── escalations_total{reason}      [Counter]
├── events_skipped_total{reason}   [Counter]
├── vl_failovers_total             [Counter]
├── analyze_requests_total{source} [Counter]
├── escalation_latency_ms          [Histogram]
├── k80_ocr_latency_ms             [Histogram]
├── pending_jobs                   [Gauge]
├── lock                           [Gauge]
├── health                         [Gauge]
├── config_state{key}              [Gauge]
├── gpu_util_percent{index}        [Gauge]
└── gpu_mem_free_gb{index}         [Gauge]
```

### HA Sensor Hierarchy

```
sensor.vision_router_*
├── queue_depth         (from /stats)
├── gpu_util            (from /stats.gpus[0].util)
├── gpu_mem_free        (from /stats.gpus[0].mem_free_gb)
├── threshold           (from /config)
├── events_total        (from /metrics)
└── escalations_total   (from /metrics)

switch.vision_*
├── on                  (POST /config {"vision_on": bool})
├── screen_watch_on     (POST /config {"screen_watch_on": bool})
└── escalate_vl         (POST /config {"escalate_vl": bool})
```

## Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         K80 VM (192.168.2.X)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐  │
│  │ vision-gateway │   │ realworld-gw   │   │ vision-router  │  │
│  │ :8051          │   │ :8052          │   │ :8050          │  │
│  │ GPU #0         │   │ GPU #1         │   │ CPU + NVML     │  │
│  └────────────────┘   └────────────────┘   └────────────────┘  │
│                                                                  │
│  Network: hassistant_v2_default (external)                      │
│  Volumes: k80-cache, streams                                    │
│  Runtime: nvidia (all services)                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (network bridge)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Main Host (192.168.2.13)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐  │
│  │ orchestrator   │   │ ollama-vl      │   │ ollama-text    │  │
│  │ :8020          │   │ :11434         │   │ :11435         │  │
│  │ CPU            │   │ 1080 Ti        │   │ 1070           │  │
│  └────────────────┘   └────────────────┘   └────────────────┘  │
│                                                                  │
│  ┌────────────────┐   ┌────────────────┐                        │
│  │ postgres       │   │ home-assistant │                        │
│  │ :5432          │   │ :8123          │                        │
│  └────────────────┘   └────────────────┘                        │
│                                                                  │
│  Network: hassistant_v2_default                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Performance Budget

| Operation | Target | Max |
|-----------|--------|-----|
| /events (no escalate) | <5ms | 20ms |
| /events (with escalate) | 2-10s | 60s |
| /analyze | 2-10s | 60s |
| /stats | <10ms | 50ms |
| /config GET | <5ms | 20ms |
| /config POST | <10ms | 50ms |
| GPU poll cycle | 5s | 10s |
| Backpressure check | <1ms | 5ms |

## Resource Limits

| Resource | Soft Limit | Hard Limit |
|----------|------------|------------|
| Queue depth | 5 jobs | 20 jobs |
| GPU utilization | 85% (60s avg) | 95% |
| Memory usage | 200MB | 500MB |
| Concurrent escalations | 1 | 3 |
| VL timeout | 60s | 120s |
| OCR hint text | 4000 chars | 8000 chars |

---

**Document Version:** 1.0
**Last Updated:** 2025-10-16
**Architecture Owner:** Workstream B (Vision Router)
