# Overnight Intelligence System - Quick Reference

## Quick Commands

```bash
# Run overnight cycle
./run_overnight.sh

# Run with Docker Compose
docker-compose run --rm overnight-crew python -m overnight

# Run tests
pytest overnight/test_overnight.py -v

# Use example client
python example_overnight_client.py
```

## Architecture

```
overnight/
├── orchestrator.py          # Main coordinator
├── schemas.py               # Data models (Pydantic)
├── artifacts.py             # Artifact storage
├── guards.py                # Safety & validation
├── crews/
│   ├── information_enrichment.py    # Web research
│   └── memory_consolidation.py      # Memory analysis
└── tools/
    ├── memory_tools.py      # Letta Bridge API
    ├── calendar_tools.py    # Home Assistant Calendar
    └── web_tools.py         # Web search & scraping
```

## Integration Points

### Letta Memory Bridge
```python
from overnight.tools import memory_tools

# Add memory
await memory_tools.add_memory(
    title="Event",
    content="Description",
    mem_type="event",
    tier="medium"
)

# Search memories
results = await memory_tools.search_memories(
    query="automation",
    k=5
)
```

### Home Assistant Calendar
```python
from overnight.tools import calendar_tools

# Get events
events = await calendar_tools.get_upcoming_events(days=7)

# Create event
await calendar_tools.create_calendar_event(
    calendar_entity="calendar.personal",
    summary="Task",
    start=datetime.now(),
    end=datetime.now() + timedelta(hours=1)
)
```

### Information Enrichment
```python
from overnight.crews import InformationEnrichmentCrew

crew = InformationEnrichmentCrew()
result = await crew.enrich_topic(
    topic="home automation",
    max_sources=3
)
```

### Memory Consolidation
```python
from overnight.crews import MemoryConsolidationCrew

crew = MemoryConsolidationCrew()
result = await crew.consolidate_memories(
    time_window_hours=24
)
```

## Scheduling

### Cron (Recommended)
```bash
# Edit crontab
crontab -e

# Add line (runs at 3 AM daily)
0 3 * * * cd /path/to/HAssistant && ./run_overnight.sh
```

### Home Assistant Automation
```yaml
# automations.yaml
- id: overnight_daily
  alias: "Overnight Intelligence - Daily"
  trigger:
    platform: time
    at: "03:00:00"
  action:
    service: shell_command.run_overnight_intelligence

# configuration.yaml
shell_command:
  run_overnight_intelligence: '/bin/bash /path/to/HAssistant/run_overnight.sh'
```

### Python Scheduler
```python
import schedule
import asyncio
from overnight.orchestrator import OvernightOrchestrator

def run_overnight():
    orchestrator = OvernightOrchestrator()
    asyncio.run(orchestrator.run_overnight_cycle())

# Schedule for 3 AM daily
schedule.every().day.at("03:00").do(run_overnight)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Environment Variables

```bash
# Letta Bridge
LETTA_BRIDGE_URL=http://hassistant-letta-bridge:8081
BRIDGE_API_KEY=your-secure-key

# Home Assistant
HA_BASE_URL=http://homeassistant:8123
HA_TOKEN=your-ha-token

# Artifacts
ARTIFACTS_DIR=/data/artifacts
```

## Output Example

```
Starting Overnight Intelligence System
Running memory consolidation...
Running calendar review...
Running memory maintenance...
=== Overnight Cycle Results ===
Cycle ID: abc-123-def
Duration: 15.23s
Tasks Completed: memory_consolidation, calendar_review, memory_maintenance
Insights Generated: 3
  - Multiple event events recorded (2 occurrences)
  - Found 1 high-confidence memories
  - Common themes: automation, lighting
Upcoming Events: 5
Memories Evicted: 12
===============================
```

## Testing

```bash
# Run all tests
pytest overnight/test_overnight.py -v

# Run specific test
pytest overnight/test_overnight.py::test_task_creation -v

# With coverage
pytest overnight/test_overnight.py --cov=overnight --cov-report=html
```

## Docker

```bash
# Build service
docker-compose build overnight-crew

# Run once
docker-compose run --rm overnight-crew python -m overnight

# View logs (if running as service)
docker-compose logs -f overnight-crew

# Access shell
docker-compose run --rm overnight-crew bash
```

## Troubleshooting

### Issue: Import errors
**Fix:** Ensure you're in the project root directory

### Issue: Letta Bridge connection failed
**Fix:** Check service is running: `docker-compose ps letta-bridge`

### Issue: Home Assistant connection failed
**Fix:** Verify HA_TOKEN is set and valid

### Issue: Rate limit exceeded
**Fix:** Adjust limits in guards.py or wait before retrying

## File Locations

- **Source:** `/home/runner/work/HAssistant/HAssistant/overnight/`
- **Artifacts:** `/data/artifacts/` (in container)
- **Logs:** stdout/stderr (capture with `>> log.txt`)
- **Tests:** `overnight/test_overnight.py`
- **Docs:** `OVERNIGHT_INTEGRATION.md`

## Links

- [Full Documentation](OVERNIGHT_INTEGRATION.md)
- [Memory Integration](MEMORY_INTEGRATION.md)
- [Main README](README.md)

## Support

For issues:
1. Check logs: `docker-compose logs overnight-crew`
2. Run tests: `pytest overnight/test_overnight.py -v`
3. Check examples: `python example_overnight_client.py`
4. Review guard rails: Ensure rate limits not exceeded
