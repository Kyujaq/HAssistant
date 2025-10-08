# Tesla K80 Quick Reference

Quick command reference for Tesla K80 GPU management.

## Detection & Discovery

```bash
# Detect K80 GPUs
make k80-detect

# Auto-discover and set env vars
eval $(python3 scripts/k80_env.py)

# Or using bash script
source <(bash scripts/k80_discover.sh)
```

## Service Management

```bash
# Build vision-worker image
make k80-build

# Start both workers
make k80-up

# Stop workers
make k80-down

# Restart workers
make k80-down && make k80-up

# View logs
make k80-logs

# View logs for specific worker
docker logs -f vision-worker-screen
docker logs -f vision-worker-room
```

## Health & Testing

```bash
# Quick warmup test
make k80-warmup

# Check worker health
make k80-health

# Or manually
curl http://localhost:8089/health | jq  # screen
curl http://localhost:8090/health | jq  # room

# 10-minute burn-in test
make k80-burnin

# Custom burn-in duration
STRESS_MINUTES=5 bash scripts/k80_burnin.sh
```

## Monitoring

```bash
# Real-time GPU stats (updates every 1s)
make k80-stats

# Manual nvidia-smi
nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used --format=csv

# Watch specific GPUs
watch -n 1 nvidia-smi -i 2,3
```

## API Testing

```bash
# Test frame processing
curl -X POST http://localhost:8089/process/frame \
  -F "file=@/path/to/image.jpg" | jq

# Test OCR
curl -X POST http://localhost:8089/ocr/crop \
  -F "file=@/path/to/text.jpg" | jq

# Test verification endpoint (vision-gateway)
curl -X POST http://localhost:8088/verify/excel \
  -F "file=@/path/to/excel_screenshot.png" | jq
```

## Integration Tests

```bash
# Run integration tests
python3 tests/test_vision_workers.py

# Test with custom URLs
VISION_SCREEN_URL=http://192.168.1.100:8089 \
VISION_ROOM_URL=http://192.168.1.100:8090 \
python3 tests/test_vision_workers.py
```

## Configuration

```bash
# Set GPU devices in .env
cat >> .env <<EOF
VISION_SCREEN_CUDA_DEVICE=2
VISION_ROOM_CUDA_DEVICE=3
EOF

# Or export for current session
export VISION_SCREEN_CUDA_DEVICE=2
export VISION_ROOM_CUDA_DEVICE=3
```

## Troubleshooting

```bash
# Check GPU visibility in container
docker run --rm --gpus device=2 nvidia/cuda:11.4.3-base nvidia-smi

# Check worker startup logs
docker logs vision-worker-screen 2>&1 | head -50

# Rebuild without cache
docker build --no-cache -t hassistant/vision-worker:latest ./services/vision-worker/

# Test GPU access manually
docker run --rm -it --gpus device=2 \
  -e VISION_CUDA_DEVICE=2 \
  hassistant/vision-worker:latest \
  python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

## Performance Tuning

```bash
# Enable persistence mode (requires sudo)
sudo nvidia-smi -pm 1

# Disable ECC for more VRAM (optional, requires reboot)
sudo nvidia-smi -i 2 --ecc-config=0
sudo nvidia-smi -i 3 --ecc-config=0
sudo reboot

# Set power limit (increase for more performance)
sudo nvidia-smi -i 2 -pl 250
sudo nvidia-smi -i 3 -pl 250

# Check power limits
nvidia-smi --query-gpu=index,power.limit,power.draw --format=csv
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_SCREEN_CUDA_DEVICE` | `2` | GPU index for screen worker |
| `VISION_ROOM_CUDA_DEVICE` | `3` | GPU index for room worker |
| `VISION_CUDA_DEVICE` | - | Set per container (auto-assigned) |
| `VISION_ROLE` | - | Worker role: `screen` or `room` |
| `PORT` | `8089`/`8090` | HTTP API port |
| `STRESS_MINUTES` | `10` | Burn-in test duration |
| `MAX_TEMP` | `82` | Max GPU temperature (°C) |

## Docker Compose Commands

```bash
# Start only vision workers
docker compose up -d vision-screen vision-room

# View worker status
docker compose ps vision-screen vision-room

# Scale workers (if needed)
docker compose up -d --scale vision-screen=2

# Stop and remove
docker compose down vision-screen vision-room
```

## One-Liners

```bash
# Full setup from scratch
make k80-detect && make k80-build && make k80-warmup && make k80-up

# Quick health check
curl -s http://localhost:8089/health | jq '.ok, .gpu_name, .temp_c'

# Monitor temps continuously
watch -n 2 'nvidia-smi -i 2,3 --query-gpu=temperature.gpu --format=csv,noheader'

# Check if workers are using GPU
docker logs vision-worker-screen 2>&1 | grep -i "gpu\|cuda"

# Test all workers
for port in 8089 8090; do echo "=== Worker on port $port ==="; curl -s http://localhost:$port/health | jq '.role, .gpu_name, .device'; done
```

## See Also

- [Complete K80 Guide](k80.md) - Full setup and troubleshooting
- [Vision Worker README](../services/vision-worker/README.md) - Service docs
- [Makefile](../Makefile) - All available targets
