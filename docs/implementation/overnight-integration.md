# Overnight Intelligence System - Integration Guide

This guide explains how to integrate and use the overnight intelligence system with HAssistant.

## Overview

The overnight intelligence system provides:
- **Memory Consolidation**: Analyzes and consolidates memories from the past 24 hours
- **Information Enrichment**: Gathers and enriches information on topics of interest
- **Calendar Integration**: Reviews upcoming events and creates reminders
- **Automated Maintenance**: Cleans up old memories and performs system maintenance

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Overnight Intelligence System                  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Orchestrator                                      │  │
│  │  - Task scheduling                                 │  │
│  │  - Crew coordination                               │  │
│  │  - Error handling                                  │  │
│  └─────────────┬─────────────────────────────────────┘  │
│                │                                          │
│        ┌───────┴────────┬────────────┐                  │
│        ▼                ▼            ▼                   │
│  ┌─────────┐    ┌─────────────┐  ┌──────────┐          │
│  │ Memory  │    │ Information │  │ Calendar │          │
│  │  Cons.  │    │ Enrichment  │  │  Tools   │          │
│  └────┬────┘    └──────┬──────┘  └────┬─────┘          │
└───────┼────────────────┼──────────────┼─────────────────┘
        │                │              │
        ▼                ▼              ▼
┌────────────────────────────────────────────────────────┐
│  Letta Bridge         Web APIs      Home Assistant     │
│  - Memory storage     - DuckDuckGo  - Calendar         │
│  - Semantic search    - Web content - Events           │
│  - Maintenance        - Research    - Automation       │
└────────────────────────────────────────────────────────┘
```

## Installation

### 1. Build the Overnight Service

```bash
cd /path/to/HAssistant
docker-compose build overnight-crew
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Already configured - verify these exist:
BRIDGE_API_KEY=your-secure-api-key
HA_TOKEN=your-home-assistant-token

# Optional:
ARTIFACTS_DIR=/data/artifacts
```

### 3. Test the Service

```bash
# Test run
docker-compose run --rm overnight-crew python -m overnight
```

Expected output:
```
Starting Overnight Intelligence System
Running memory consolidation...
Reviewing calendar...
Running memory maintenance...
=== Overnight Cycle Results ===
Cycle ID: abc-123-def
Duration: 15.23s
Tasks Completed: memory_consolidation, calendar_review, memory_maintenance
===============================
```

## Usage

### Method 1: Manual Execution

Run the overnight cycle manually:

```bash
./run_overnight.sh
```

Or using Docker Compose directly:

```bash
docker-compose run --rm overnight-crew python -m overnight
```

### Method 2: Scheduled via Cron

Add to your crontab:

```bash
# Run overnight tasks daily at 3 AM
0 3 * * * cd /path/to/HAssistant && ./run_overnight.sh >> /var/log/overnight.log 2>&1
```

### Method 3: Home Assistant Automation

Add to your Home Assistant `automations.yaml`:

```yaml
# Overnight Intelligence System - Daily Run
- id: overnight_intelligence_daily
  alias: "Overnight Intelligence - Daily Cycle"
  trigger:
    - platform: time
      at: "03:00:00"
  action:
    - service: shell_command.run_overnight_intelligence
      
# Optional: Run on demand
- id: overnight_intelligence_on_demand
  alias: "Overnight Intelligence - On Demand"
  trigger:
    - platform: event
      event_type: run_overnight_intelligence
  action:
    - service: shell_command.run_overnight_intelligence
```

Add to `configuration.yaml`:

```yaml
shell_command:
  run_overnight_intelligence: '/bin/bash /path/to/HAssistant/run_overnight.sh'
```

### Method 4: Python API

Use the orchestrator directly:

```python
import asyncio
from overnight.orchestrator import OvernightOrchestrator

async def main():
    orchestrator = OvernightOrchestrator()
    
    # Run full cycle
    results = await orchestrator.run_overnight_cycle()
    print(f"Completed {len(results['tasks_completed'])} tasks")
    
    # Or schedule individual tasks
    task_id = await orchestrator.schedule_enrichment(
        query="smart home automation trends",
        max_results=5
    )
    print(f"Scheduled enrichment task: {task_id}")
    
    # Check task status
    status = orchestrator.get_task_status(task_id)
    print(f"Task status: {status['status']}")

asyncio.run(main())
```

## Features

### Memory Consolidation

The system automatically:
- Reviews memories from the past 24 hours
- Identifies patterns and generates insights
- Consolidates related memories
- Promotes important memories to higher tiers
- Saves consolidated insights back to memory

Example insights:
- "Multiple event events recorded (3 occurrences)"
- "Found 2 high-confidence memories"
- "Common themes: automation, lighting, security"

### Information Enrichment

Gather and enrich information on any topic:

```python
from overnight.crews import InformationEnrichmentCrew

crew = InformationEnrichmentCrew()
result = await crew.enrich_topic(
    topic="home energy efficiency",
    max_sources=3
)

print(f"Summary: {result.summary}")
print(f"Artifacts: {len(result.artifacts)}")
```

Features:
- Web search using DuckDuckGo
- Content fetching and extraction
- Artifact creation with metadata
- Automatic memory storage
- Confidence scoring

### Calendar Integration

Review and manage calendar events:

```python
from overnight.tools import calendar_tools

# Get upcoming events
events = await calendar_tools.get_upcoming_events(days=7)
print(f"Found {len(events)} upcoming events")

# Create event
await calendar_tools.create_calendar_event(
    calendar_entity="calendar.personal",
    summary="Weekly Review",
    start=datetime(2024, 10, 10, 14, 0),
    end=datetime(2024, 10, 10, 15, 0),
    description="Review overnight intelligence reports"
)
```

### Memory Maintenance

Automatic cleanup:
- Evicts old memories based on tier policies
- Respects pinned memories
- Runs database maintenance
- Logs eviction statistics

## Configuration

### Guard Rails

The system includes built-in safety mechanisms:

```python
from overnight.guards import GuardRails

guards = GuardRails()

# Content validation
guards.validate_memory_content(content)  # Max 10KB

# URL validation
guards.validate_web_url(url)  # Blocks localhost, private IPs

# Rate limiting
guards.check_rate_limit("operation", max_per_hour=100, max_per_minute=10)
```

### Artifact Storage

Artifacts are stored locally in JSON format:

```bash
/data/artifacts/
  ├── abc-123-def.json
  ├── xyz-456-ghi.json
  └── ...
```

Each artifact contains:
- Unique ID
- Source task ID
- Type (research, insight, etc.)
- Title and content
- Metadata and tags
- Confidence score
- Creation timestamp

## Integration with Existing Services

### GLaDOS Orchestrator

The overnight system complements the orchestrator:

```
Query → GLaDOS Orchestrator → [Qwen/Hermes] → Response
                ↓
         Letta Bridge (shared)
                ↑
         Overnight System → Background tasks
```

Both services:
- Share the same Letta Bridge instance
- Use the same memory tiers
- Coordinate through memory pins
- Respect rate limits

### Qwen-Agent Integration

The overnight system follows Qwen-Agent patterns:

```python
# Crew-based architecture (like Qwen-Agent)
class InformationEnrichmentCrew:
    def __init__(self):
        self.artifact_manager = ArtifactManager()
        self.guards = GuardRails()
        
    async def enrich_topic(self, topic: str):
        # 1. Validate
        # 2. Execute tools
        # 3. Create artifacts
        # 4. Store results
        pass
```

Benefits:
- Familiar patterns for Qwen-Agent users
- Tool-based architecture
- Async/await support
- Type hints with Pydantic

## Monitoring

### Logs

View logs in real-time:

```bash
docker-compose logs -f overnight-crew
```

### Task Status

Check task status programmatically:

```python
orchestrator = OvernightOrchestrator()

# List all tasks
tasks = orchestrator.list_tasks(limit=10)

# Check specific task
status = orchestrator.get_task_status(task_id)
print(f"Status: {status['status']}")
print(f"Started: {status['started_at']}")
print(f"Completed: {status['completed_at']}")
```

### Memory Metrics

Query Letta Bridge for memory statistics:

```bash
curl -H "x-api-key: your-key" http://localhost:8081/metrics
```

## Troubleshooting

### Issue: Tasks timing out

**Solution**: Increase timeout in guards or reduce scope:

```python
# In guards.py, adjust rate limits
guards.check_rate_limit("operation", max_per_hour=50)  # Reduce
```

### Issue: Memory not persisting

**Solution**: Check Letta Bridge connection:

```bash
docker-compose logs letta-bridge
curl -H "x-api-key: your-key" http://localhost:8081/healthz
```

### Issue: Calendar integration not working

**Solution**: Verify HA_TOKEN is set:

```bash
# Test Home Assistant API
curl -H "Authorization: Bearer $HA_TOKEN" \
     http://homeassistant:8123/api/
```

### Issue: Web search failing

**Solution**: Check network connectivity and try alternative sources:

```python
# Fallback to manual content
from overnight.tools import web_tools
content = await web_tools.fetch_url_content("https://example.com")
```

## Best Practices

1. **Schedule during low-activity periods** (e.g., 3 AM)
2. **Monitor logs regularly** for errors
3. **Adjust rate limits** based on your needs
4. **Pin important memories** to prevent eviction
5. **Review consolidated insights** weekly
6. **Test changes** in development first
7. **Backup artifact directory** regularly

## Example Workflows

### Daily Intelligence Briefing

```python
async def daily_briefing():
    orchestrator = OvernightOrchestrator()
    results = await orchestrator.run_overnight_cycle()
    
    # Get consolidated insights
    insights = results.get('consolidation_insights', [])
    
    # Format for notification
    message = "Daily Intelligence Brief:\n"
    for insight in insights:
        message += f"- {insight}\n"
    
    # Send to Home Assistant
    # (via notify service or display on dashboard)
    return message
```

### Automated Research

```python
async def research_topics():
    orchestrator = OvernightOrchestrator()
    
    topics = [
        "smart home security trends",
        "home automation best practices",
        "energy efficiency tips"
    ]
    
    for topic in topics:
        await orchestrator.schedule_enrichment(
            query=topic,
            max_results=3
        )
```

### Weekly Memory Cleanup

```python
async def weekly_cleanup():
    from overnight.tools import memory_tools
    
    # Run maintenance
    results = await memory_tools.run_maintenance()
    
    print(f"Evicted {results['total_evicted']} old memories")
    print(f"By tier: {results['by_tier']}")
```

## Future Enhancements

Planned features:
- [ ] Integration with more calendar providers
- [ ] Advanced NLP for insight generation
- [ ] Custom research sources
- [ ] Machine learning for importance scoring
- [ ] Multi-language support
- [ ] REST API for external integrations
- [ ] Web UI for monitoring

## Support

For issues or questions:
1. Check logs: `docker-compose logs overnight-crew`
2. Review tests: `pytest overnight/test_overnight.py -v`
3. Check GitHub issues
4. Review MEMORY_INTEGRATION.md for Letta Bridge details

## License

Same as HAssistant project.