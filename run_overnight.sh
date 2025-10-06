#!/bin/bash
# Run overnight intelligence system
# This script can be scheduled via cron or Home Assistant automation

echo "Starting overnight intelligence cycle..."
docker-compose run --rm overnight-crew python -m overnight

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "Overnight cycle completed successfully"
else
    echo "Overnight cycle failed with exit code $exit_code"
fi

exit $exit_code
