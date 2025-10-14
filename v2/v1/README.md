# Legacy Data Placeholder

This directory is mounted into the `memory-backfill` container so it can read
historical notes/logs from the legacy v1 stack. If you still have the original
`v1/` checkout from the previous release, either copy it here or update the
bind mount in `v2/docker-compose.yml` to point to the real dataset before
running the backfill job.
