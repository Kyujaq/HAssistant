# Kitchen Stack Nightly Pipeline - Quick Start

This guide shows you how to run the kitchen stack nightly pipeline orchestrator.

## What It Does

The nightly pipeline orchestrates three agents in sequence:
1. **Paprika Sync** - Fetches recipes and meal plans
2. **Inventory** - Updates kitchen inventory
3. **Dietitian** - Analyzes nutritional data

Each run creates timestamped artifacts in `/data/artifacts/YYYY-MM-DD/`.

## Running the Pipeline

### Option 1: Docker Compose (Recommended)

```bash
# Run once
docker compose --profile manual up kitchen-nightly

# Run in background
docker compose --profile manual up -d kitchen-nightly

# View logs
docker compose logs -f kitchen-nightly
```

### Option 2: Docker Directly

```bash
# Build the image
docker build -t kitchen-nightly -f Dockerfile .

# Run with volume mount
docker run --rm \
  -v $(pwd)/data:/data \
  -e TZ=America/Toronto \
  kitchen-nightly
```

### Option 3: Python Directly (Development)

```bash
# Create data directory
mkdir -p ./data/artifacts

# Run the pipeline
export DATA_DIR=$(pwd)/data
python3 orchestrator/nightly.py
```

## Setting Up Scheduled Runs

### Using Cron (Linux/Mac)

Add to your crontab (`crontab -e`):

```bash
# Run nightly at 2:00 AM
0 2 * * * cd /path/to/HAssistant && docker compose --profile manual up kitchen-nightly >> /var/log/kitchen-nightly.log 2>&1
```

### Using systemd Timer (Linux)

1. Create `/etc/systemd/system/kitchen-nightly.service`:
```ini
[Unit]
Description=Kitchen Stack Nightly Pipeline
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/HAssistant
ExecStart=/usr/bin/docker compose --profile manual up kitchen-nightly
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

2. Create `/etc/systemd/system/kitchen-nightly.timer`:
```ini
[Unit]
Description=Run Kitchen Stack Nightly Pipeline
Requires=kitchen-nightly.service

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

3. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kitchen-nightly.timer
sudo systemctl start kitchen-nightly.timer
```

## Checking Results

```bash
# View today's artifacts
ls -la ./data/artifacts/$(date +%Y-%m-%d)/

# Read pipeline summary
cat ./data/artifacts/$(date +%Y-%m-%d)/pipeline_summary.json

# View logs
docker compose logs kitchen-nightly
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATA_DIR` | Base directory for artifacts | `/data` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `TZ` | Timezone for timestamps | `America/Toronto` |

## Troubleshooting

### Pipeline fails to start

**Check Docker and compose are working:**
```bash
docker --version
docker compose version
```

### Permission denied on /data

**Ensure the data directory is writable:**
```bash
mkdir -p ./data
chmod 755 ./data
```

### Missing artifacts

**Check if the directory was created:**
```bash
ls -la ./data/artifacts/$(date +%Y-%m-%d)/
```

**Check container logs:**
```bash
docker compose logs kitchen-nightly
```

## Next Steps

The current implementation creates placeholder artifacts. As you implement the actual agents:

1. Update `run_paprika_sync()` to fetch real Paprika data
2. Update `run_inventory()` to sync with your inventory database
3. Update `run_dietitian()` to perform real nutritional analysis

See `orchestrator/README.md` for development details.
