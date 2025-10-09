# Overnight Intelligence System

This module contains the overnight intelligence system for HAssistant.

## Overview

The overnight intelligence system runs background tasks for:
- Information enrichment
- Memory consolidation
- Calendar integration
- Web research

## Components

### Core Modules
- `orchestrator.py` - Main orchestration logic
- `schemas.py` - Data schemas and models (Pydantic)
- `artifacts.py` - Artifact management
- `guards.py` - Guard rails and validation

### Crews
- `crews/information_enrichment.py` - Information gathering and enrichment
- `crews/memory_consolidation.py` - Memory processing and consolidation

### Tools
- `tools/calendar_tools.py` - Calendar integration tools (Home Assistant)
- `tools/memory_tools.py` - Memory management tools (Letta Bridge)
- `tools/web_tools.py` - Web research and scraping tools

## Architecture Integration

The overnight system integrates with:

### Home Assistant
- Calendar events via HA REST API
- State changes and automations
- Service calls for system integration

### GLaDOS Orchestrator
- Memory storage for enrichment results
- Query processing coordination
- Shared Letta Bridge access

### Letta Memory
- Persistent memory storage
- Semantic search capabilities
- Memory consolidation and maintenance

### Qwen-Agent Framework
- Task execution using agent patterns
- Tool integration
- Crew-based operations

## Usage

### Running Overnight Cycle

```python
from overnight.orchestrator import OvernightOrchestrator

orchestrator = OvernightOrchestrator()
results = await orchestrator.run_overnight_cycle()
```

### Scheduling Tasks

```python
# Schedule information enrichment
task_id = await orchestrator.schedule_enrichment(
    query="home automation trends",
    max_results=5
)

# Schedule memory consolidation
task_id = await orchestrator.schedule_consolidation(
    time_window_hours=24,
    min_confidence=0.7
)

# Check task status
status = orchestrator.get_task_status(task_id)
```

### Using Individual Crews

```python
from overnight.crews import InformationEnrichmentCrew, MemoryConsolidationCrew

# Information enrichment
enrichment_crew = InformationEnrichmentCrew()
result = await enrichment_crew.enrich_topic("AI assistants", max_sources=3)

# Memory consolidation
consolidation_crew = MemoryConsolidationCrew()
consolidated = await consolidation_crew.consolidate_memories(time_window_hours=24)
```

## Configuration

Environment variables:

```bash
# Letta Bridge
LETTA_BRIDGE_URL=http://hassistant-letta-bridge:8081
BRIDGE_API_KEY=your-api-key

# Home Assistant
HA_BASE_URL=http://homeassistant:8123
HA_TOKEN=your-ha-token

# Artifacts
ARTIFACTS_DIR=/data/artifacts
```

## Testing

Run tests with:
```bash
pytest overnight/test_overnight.py -v
```

## Task Types

### Enrichment Tasks
- Web research on topics
- Information gathering from multiple sources
- Artifact creation
- Memory storage

### Consolidation Tasks
- Memory pattern analysis
- Insight generation
- Memory tier promotion
- Related memory linking

### Calendar Tasks
- Event retrieval
- Event creation
- Upcoming event analysis
- Calendar-based reminders

## Memory Tiers

The system uses Letta's tiered memory model:

- **Session**: Current conversation only
- **Short**: Minutes to hours (auto-evicted)
- **Medium**: Days to weeks
- **Long**: Weeks to months
- **Permanent**: Never auto-evicted (pinned)

## Guard Rails

The system includes safety mechanisms:

- Content validation (length, sensitive data detection)
- Rate limiting (per-minute and per-hour)
- URL validation (blocked domains, protocols)
- Task validation (required fields, types)
- Calendar event validation

## Artifact Management

Artifacts are enrichment results stored locally:

- JSON-based storage
- Metadata and tagging
- Confidence scoring
- Source tracking
- Filtering and search

## Integration Example

```python
# Complete workflow
from overnight.orchestrator import OvernightOrchestrator

async def daily_overnight_routine():
    orchestrator = OvernightOrchestrator()
    
    # Run full overnight cycle
    results = await orchestrator.run_overnight_cycle()
    
    print(f"Completed {len(results['tasks_completed'])} tasks")
    print(f"Insights: {results.get('consolidation_insights', [])}")
    print(f"Upcoming events: {results.get('upcoming_events_count', 0)}")
    
    return results
```

## Notes

This system is designed to run as a background service, typically scheduled during
low-activity periods (overnight) to perform maintenance, consolidation, and enrichment
tasks without impacting real-time assistant performance.
