# Kitchen Stack Orchestrator

The orchestrator is the main application entrypoint that runs the nightly pipeline by calling different agent modules in sequence.

## Overview

The nightly pipeline processes kitchen-related data through various agents:
1. **Paprika Sync** - Fetches recipes and meal plans from Paprika API
2. **Inventory** - Updates kitchen inventory based on purchases and consumption
3. **Dietitian** - Analyzes nutritional data and provides recommendations

## Usage

### Running Locally

```bash
# Set the data directory (defaults to /data)
export DATA_DIR=/path/to/data

# Run the pipeline
python3 orchestrator/nightly.py
```

### Running with Docker

```bash
# Build the image
docker build -t kitchen-nightly -f Dockerfile .

# Run the container with volume mount
docker run --rm -v ./data:/data -e TZ=America/Toronto kitchen-nightly
```

### Running with Docker Compose

```bash
# Run the nightly pipeline
docker compose --profile manual up kitchen-nightly

# Or run in detached mode
docker compose --profile manual up -d kitchen-nightly
```

## Configuration

The orchestrator uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATA_DIR` | Base directory for artifacts | `/data` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `TZ` | Timezone for timestamps | `America/Toronto` |

## Artifacts

The pipeline creates timestamped directories for each run:

```
/data/artifacts/
  ├── 2025-01-15/
  │   ├── paprika_snapshot.json
  │   ├── inventory_snapshot.json
  │   ├── dietitian_analysis.json
  │   └── pipeline_summary.json
  └── 2025-01-16/
      └── ...
```

## Pipeline Flow

```
┌─────────────────────┐
│  Start Pipeline     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Create Artifact Dir │
│  /data/artifacts/   │
│    YYYY-MM-DD/      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Paprika Sync       │
│  (Agent 1)          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Inventory Update   │
│  (Agent 2)          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Dietitian Analysis │
│  (Agent 3)          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Pipeline Summary   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Exit (0=success)   │
└─────────────────────┘
```

## Error Handling

- Each agent step logs its progress
- If any step fails, the pipeline exits with a non-zero status code
- Error messages are logged with full stack traces
- Partial artifacts are still saved even if the pipeline fails

## Development

### Adding New Agents

1. Create a new agent function in `nightly.py`:
   ```python
   def run_new_agent(artifact_dir: Path) -> bool:
       """Agent description."""
       logger.info("=" * 60)
       logger.info("STEP X: New Agent")
       logger.info("=" * 60)
       # Implementation here
       return success
   ```

2. Add the agent to the pipeline in `run_pipeline()`:
   ```python
   results["new_agent"] = run_new_agent(artifact_dir)
   if not results["new_agent"]:
       logger.error("Pipeline failed at New Agent step")
       return 1
   ```

### Testing

```bash
# Test with a temporary data directory
mkdir -p /tmp/test_data
DATA_DIR=/tmp/test_data python3 orchestrator/nightly.py

# Check the artifacts
ls -la /tmp/test_data/artifacts/$(date +%Y-%m-%d)/
```

## Future Enhancements

- [ ] Implement actual agent logic (Paprika, Inventory, Dietitian)
- [ ] Add retry logic for failed steps
- [ ] Implement parallel agent execution where possible
- [ ] Add notification system for pipeline failures
- [ ] Add metrics and monitoring
- [ ] Implement incremental updates instead of full snapshots
