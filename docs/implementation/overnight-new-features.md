# New Overnight Crew Features - Documentation

This document describes the three new high-impact features added to the Overnight Intelligence System.

## Overview

The Overnight Crew has been enhanced with three powerful new capabilities:

1. **Intelligent Commute & Travel Preparation** - Proactively analyzes traffic conditions for calendar events
2. **Deep Home Energy Analysis** - Analyzes energy consumption patterns and identifies optimization opportunities
3. **Task & Project Priming** - Automatically researches and prepares briefings for to-do list items

## Feature #1: Intelligent Commute & Travel Preparation

### Purpose
Predicts future traffic conditions for calendar events and provides proactive travel alerts to help users plan their commutes effectively.

### Components

#### CommutePlannerAgent
Located in `overnight/crews/proactive_planning.py`

- Analyzes calendar events with physical locations
- Predicts travel times using traffic data
- Generates alerts when traffic exceeds normal conditions by a configurable threshold (default: 20%)
- Calculates recommended departure times with buffer

#### TrafficAnalysisTool
Located in `overnight/tools/traffic_tools.py`

**Functions:**
- `get_predicted_travel_time()` - Gets predicted travel duration for a future time
  - Supports Google Maps API integration
  - Falls back to intelligent mock data based on time of day
  - Parameters: origin, destination, departure_time, traffic_model
  
- `analyze_commute_impact()` - Analyzes if traffic warrants an alert
  - Compares predicted vs. baseline travel times
  - Returns severity level and reasoning

#### CommuteAlert Schema
Located in `overnight/schemas.py`

```python
class CommuteAlert(BaseModel):
    event_title: str
    predicted_travel_time_minutes: int
    recommended_departure_time: str  # ISO format
    reasoning: str  # e.g., "Heavy traffic expected on I-5"
    origin: Optional[str]
    destination: Optional[str]
    baseline_time_minutes: Optional[int]
```

### Usage Example

```python
from overnight.crews.proactive_planning import ProactivePlanningCrew

crew = ProactivePlanningCrew()
result = await crew.run_daily_planning(
    user_location="Home",  # From device_tracker entity
    todo_entity_id="todo.tasks",
    days_ahead=1
)

# Access commute alerts
for alert in result.commute_alerts:
    print(f"Event: {alert.event_title}")
    print(f"Travel Time: {alert.predicted_travel_time_minutes} min")
    print(f"Depart By: {alert.recommended_departure_time}")
    print(f"Reason: {alert.reasoning}")
```

### Configuration

Set environment variables for traffic API integration:
```bash
GOOGLE_MAPS_API_KEY=your_api_key_here  # Optional - uses mock data if not set
USER_LOCATION=Home  # Default user location
```

### Output

The ProactivePlanningOutput includes:
- `calendar_events`: List of tomorrow's events
- `commute_alerts`: List of CommuteAlert objects
- `research_briefings`: Dict of task briefings
- `summary`: Text summary of planning results

## Feature #2: Deep Home Energy Analysis

### Purpose
Analyzes the previous day's energy consumption from the Home Assistant Energy Dashboard, identifies anomalies, and provides actionable insights.

### Components

#### EnergyAuditorAgent
Located in `overnight/crews/pattern_analysis.py`

- Fetches total energy consumption for last 24 hours
- Gets consumption breakdown by individual device
- Compares usage to weekly average to detect anomalies
- Correlates high-consumption periods with specific devices
- Generates human-readable insights with severity levels

#### EnergyDashboardTool
Located in `overnight/tools/energy_tools.py`

**Functions:**
- `get_energy_consumption_24h()` - Fetches total 24h consumption
- `get_device_energy_breakdown()` - Gets per-device consumption
- `get_weekly_average_consumption()` - Calculates weekly average

#### EnergyInsight Schema
Located in `overnight/schemas.py`

```python
class EnergyInsight(BaseModel):
    title: str  # e.g., "Higher Than Average HVAC Usage"
    description: str  # Detailed explanation
    severity: Literal["info", "warning"]
    device_name: Optional[str]
    energy_kwh: Optional[float]
    time_period: Optional[str]
```

### Usage Example

```python
from overnight.crews.pattern_analysis import PatternAnalysisCrew

crew = PatternAnalysisCrew()
result = await crew.run_daily_analysis()

print(f"Total Consumption: {result.total_consumption_kwh:.2f} kWh")

# Review insights
for insight in result.energy_insights:
    severity_icon = "⚠️" if insight.severity == "warning" else "ℹ️"
    print(f"{severity_icon} {insight.title}")
    print(f"   {insight.description}")
```

### Configuration

Configure Home Assistant access:
```bash
HA_BASE_URL=http://homeassistant:8123
HA_TOKEN=your_ha_long_lived_access_token
```

### Insights Generated

The agent generates several types of insights:

1. **Comparison to Average**: Alerts if consumption is >20% different from weekly average
2. **Top Consumers**: Identifies the top 3 energy-consuming devices
3. **Anomalous Devices**: Alerts if a single device uses >50% of total consumption
4. **Efficiency Recommendations**: Suggests optimization when consumption is high (>30 kWh/day)

### Output

The PatternAnalysisOutput includes:
- `energy_insights`: List of EnergyInsight objects
- `analysis_period`: Time period analyzed (e.g., "24h")
- `total_consumption_kwh`: Total energy consumed
- `summary`: Text summary of analysis

## Feature #3: Task & Project Priming

### Purpose
Automatically pre-researches items on the user's Home Assistant To-Do list, attaching relevant documents and links to prepare for the task.

### Components

#### ResearcherAgent
Located in `overnight/crews/proactive_planning.py`

- Reads to-do list items from Home Assistant
- Searches internal memory for relevant context using MemorySearchTool
- Searches web for relevant articles using WebSearchTool
- Creates markdown briefings with links and references
- Selects top 2-3 most relevant results from each source

#### TodoListTool
Located in `overnight/tools/todo_tools.py`

**Functions:**
- `get_todo_items()` - Fetches items from a To-Do list entity
- `get_upcoming_tasks()` - Gets tasks due in next N days
- `create_todo_item()` - Creates new to-do items
- `update_todo_item()` - Updates existing items

#### ResearchBriefing Schema
Located in `overnight/schemas.py`

```python
class ResearchBriefing(BaseModel):
    task_title: str
    briefing: str  # Markdown string with summary and links
    memory_ids: List[str]  # Relevant internal memory IDs
    external_urls: List[str]  # Relevant external URLs
    confidence: float  # 0.0-1.0
```

### Usage Example

```python
from overnight.crews.proactive_planning import ProactivePlanningCrew

crew = ProactivePlanningCrew()
result = await crew.run_daily_planning(
    user_location="Home",
    todo_entity_id="todo.tasks",
    days_ahead=1
)

# Access research briefings
for task_title, briefing in result.research_briefings.items():
    print(f"\nTask: {task_title}")
    print(f"Confidence: {briefing.confidence:.2f}")
    print(f"Internal References: {len(briefing.memory_ids)}")
    print(f"External Resources: {len(briefing.external_urls)}")
    print(f"\nBriefing:\n{briefing.briefing}")
```

### Configuration

```bash
TODO_ENTITY_ID=todo.tasks  # Default to-do list entity
HA_BASE_URL=http://homeassistant:8123
HA_TOKEN=your_ha_token
LETTA_BRIDGE_URL=http://hassistant-letta-bridge:8081
BRIDGE_API_KEY=your_bridge_api_key
```

### Briefing Format

Research briefings are generated in Markdown format:

```markdown
# Research Briefing: Task Title

## Task Description
[Task description if available]

## Relevant Internal Notes
- **Memory Title** (ID: `abc-123`)
  Preview of memory content...

## Relevant External Resources
- [Article Title](https://example.com)
  Summary of the article...

## No Resources Found
[Shown if no relevant resources found]
```

### Output

Research briefings are included in ProactivePlanningOutput:
- `research_briefings`: Dict mapping task titles to ResearchBriefing objects
- Each briefing includes memory IDs and external URLs for easy reference

## Integration with Orchestrator

All three features are integrated into the main overnight cycle via `OvernightOrchestrator`:

```python
from overnight.orchestrator import OvernightOrchestrator

orchestrator = OvernightOrchestrator()
results = await orchestrator.run_overnight_cycle()

# Results include:
# - commute_alerts_count: Number of commute alerts generated
# - research_briefings_count: Number of tasks researched
# - energy_insights_count: Number of energy insights
# - total_energy_kwh: Total energy consumption
# - commute_alerts: List of alert details
# - energy_insights: List of top insights
```

## Testing

### Run All Tests

```bash
# Run all overnight tests including new features
pytest overnight/test_overnight.py overnight/test_new_features.py -v

# Run only new feature tests
pytest overnight/test_new_features.py -v
```

### Test Coverage

The new features include 13 comprehensive tests:
- Schema validation tests
- Mock tool tests (traffic, energy, todo)
- Agent integration tests
- Crew integration tests
- End-to-end workflow tests

All tests pass successfully and use mock data when Home Assistant/external services are unavailable.

## Example Client

Run the example client to see all features in action:

```bash
python3 example_new_features.py
```

This demonstrates:
1. Commute planning with traffic analysis
2. Energy consumption analysis
3. Full overnight intelligence cycle

## Environment Variables Summary

```bash
# Traffic Analysis
GOOGLE_MAPS_API_KEY=optional_api_key
USER_LOCATION=Home

# Energy Analysis & To-Do Integration
HA_BASE_URL=http://homeassistant:8123
HA_TOKEN=your_long_lived_access_token
TODO_ENTITY_ID=todo.tasks

# Memory Integration
LETTA_BRIDGE_URL=http://hassistant-letta-bridge:8081
BRIDGE_API_KEY=your_secure_api_key

# Artifacts Storage
ARTIFACTS_DIR=/data/artifacts
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│           Overnight Intelligence Orchestrator            │
│  ┌───────────────────────────────────────────────────┐  │
│  │  run_overnight_cycle()                             │  │
│  │  1. Memory consolidation                           │  │
│  │  2. Proactive planning ← NEW                       │  │
│  │  3. Pattern analysis ← NEW                         │  │
│  │  4. Calendar review                                │  │
│  │  5. Memory maintenance                             │  │
│  └─────────────┬─────────────────────────────────────┘  │
└────────────────┼────────────────────────────────────────┘
                 │
        ┌────────┴────────┬────────────────┐
        ▼                 ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Proactive   │  │   Pattern    │  │    Memory    │
│  Planning    │  │   Analysis   │  │Consolidation │
│    Crew      │  │     Crew     │  │     Crew     │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
   ┌───┴────┬────┐      │
   ▼        ▼    ▼      ▼
┌────────┐ ┌──────┐ ┌─────────┐
│Commute │ │Resear│ │ Energy  │
│Planner │ │ cher │ │ Auditor │
│ Agent  │ │Agent │ │  Agent  │
└───┬────┘ └──┬───┘ └────┬────┘
    │         │          │
    ▼         ▼          ▼
┌─────────────────────────────┐
│         Tools Layer          │
│  - Traffic Analysis          │
│  - Todo List                 │
│  - Energy Dashboard          │
│  - Calendar                  │
│  - Memory Search             │
│  - Web Search                │
└──────────────┬───────────────┘
               │
        ┌──────┴─────────┬────────────┐
        ▼                ▼            ▼
┌──────────────┐  ┌────────────┐  ┌──────────┐
│ Google Maps  │  │    Home    │  │  Letta   │
│  (optional)  │  │ Assistant  │  │  Bridge  │
└──────────────┘  └────────────┘  └──────────┘
```

## Performance

The new features add minimal overhead to the overnight cycle:
- Proactive planning: ~0.3-1.0s (depending on number of events/tasks)
- Pattern analysis: ~0.1-0.3s
- Total cycle time: ~0.5-2.0s (with mock data)

With real Home Assistant and external API calls, expect:
- Proactive planning: ~2-5s
- Pattern analysis: ~1-2s  
- Total cycle time: ~5-15s

## Troubleshooting

### No Commute Alerts Generated
- Verify calendar events have `location` field set
- Check that events are in the future
- Ensure traffic threshold is appropriate (default: 20%)

### Energy Insights Not Showing
- Verify Home Assistant Energy Dashboard is configured
- Check that HA_TOKEN has proper permissions
- Ensure energy sensors exist and are updating

### Research Briefings Empty
- Verify to-do list entity exists and has items
- Check Letta Bridge connection for memory search
- Ensure web search has internet connectivity

### Tests Failing
```bash
# Install dependencies
pip install -r overnight/requirements.txt

# Run with verbose output
pytest overnight/test_new_features.py -v -s
```

## Future Enhancements

Potential improvements for future versions:
1. **Commute Planning**: Add support for multiple traffic sources (Waze, HERE Maps)
2. **Energy Analysis**: Add time-of-day consumption patterns and cost calculations
3. **Task Research**: Integrate with AI summarization for better briefings
4. **All Features**: Add support for user preferences and customizable thresholds

## API Reference

For detailed API documentation, see:
- [schemas.py](overnight/schemas.py) - All data models
- [proactive_planning.py](overnight/crews/proactive_planning.py) - Commute & research agents
- [pattern_analysis.py](overnight/crews/pattern_analysis.py) - Energy auditor agent
- [traffic_tools.py](overnight/tools/traffic_tools.py) - Traffic analysis functions
- [energy_tools.py](overnight/tools/energy_tools.py) - Energy dashboard functions
- [todo_tools.py](overnight/tools/todo_tools.py) - To-do list functions

## Support

For issues or questions:
1. Check logs: `docker-compose logs overnight-crew`
2. Run tests: `pytest overnight/test_new_features.py -v`
3. Try example: `python3 example_new_features.py`
4. Review this documentation and inline code comments
