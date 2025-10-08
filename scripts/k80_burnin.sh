#!/usr/bin/env bash
#
# Tesla K80 Burn-in Test Script
# Stress tests both K80 GPUs for stability validation
#
set -euo pipefail

# Configuration
STRESS_MINUTES=${STRESS_MINUTES:-10}
MAX_TEMP=${MAX_TEMP:-82}
SCREEN_GPU=${VISION_SCREEN_CUDA_DEVICE:-2}
ROOM_GPU=${VISION_ROOM_CUDA_DEVICE:-3}

echo "════════════════════════════════════════════════════════════"
echo "Tesla K80 Burn-in Test"
echo "════════════════════════════════════════════════════════════"
echo "Duration: ${STRESS_MINUTES} minutes"
echo "Max temp: ${MAX_TEMP}°C"
echo "Screen GPU: ${SCREEN_GPU}"
echo "Room GPU: ${ROOM_GPU}"
echo "════════════════════════════════════════════════════════════"

# Enable persistence mode for better performance
echo "Enabling GPU persistence mode..."
nvidia-smi -pm 1 || echo "⚠️  Could not enable persistence mode (may need sudo)"

# Optional: Disable ECC for performance (safe for vision workloads)
# Uncomment if you want extra performance and VRAM
# echo "Disabling ECC..."
# nvidia-smi -i ${SCREEN_GPU} --ecc-config=0 || true
# nvidia-smi -i ${ROOM_GPU} --ecc-config=0 || true

# Display initial GPU state
echo ""
echo "Initial GPU state:"
nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv
echo ""

# Start GPU monitoring in background
MONITOR_LOG="/tmp/k80_burnin_monitor.log"
echo "Starting GPU monitoring (logging to ${MONITOR_LOG})..."
(
  while true; do
    nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv
    sleep 5
  done
) > "${MONITOR_LOG}" 2>&1 &
MONITOR_PID=$!

echo "Monitor PID: ${MONITOR_PID}"

# Trap to ensure cleanup
cleanup() {
  echo ""
  echo "════════════════════════════════════════════════════════════"
  echo "Cleaning up..."
  kill ${MONITOR_PID} 2>/dev/null || true
  
  # Show final GPU state
  echo ""
  echo "Final GPU state:"
  nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used --format=csv
  echo ""
  
  # Show peak temperatures from log
  if [ -f "${MONITOR_LOG}" ]; then
    echo "Peak temperatures during test:"
    grep -E "^[0-9]+" "${MONITOR_LOG}" | awk -F',' '{print $1 ", " $3}' | sort -t',' -k2 -rn | head -5
  fi
  
  echo "════════════════════════════════════════════════════════════"
}
trap cleanup EXIT INT TERM

# Build the vision-worker image if not already built
echo "Building vision-worker image..."
docker build -t hassistant/vision-worker:latest ./services/vision-worker/

# Launch stress test containers for both K80 GPUs
echo ""
echo "Launching stress test on GPU ${SCREEN_GPU} (screen worker)..."
docker run --rm --gpus "device=${SCREEN_GPU}" \
  --name k80-stress-screen \
  -e VISION_CUDA_DEVICE=${SCREEN_GPU} \
  hassistant/vision-worker:latest \
  python3 -m app.tools.stress --device 0 --minutes ${STRESS_MINUTES} --max-temp ${MAX_TEMP} &
STRESS_SCREEN_PID=$!

echo "Launching stress test on GPU ${ROOM_GPU} (room worker)..."
docker run --rm --gpus "device=${ROOM_GPU}" \
  --name k80-stress-room \
  -e VISION_CUDA_DEVICE=${ROOM_GPU} \
  hassistant/vision-worker:latest \
  python3 -m app.tools.stress --device 0 --minutes ${STRESS_MINUTES} --max-temp ${MAX_TEMP} &
STRESS_ROOM_PID=$!

echo ""
echo "Stress tests running..."
echo "  Screen GPU ${SCREEN_GPU}: docker logs -f k80-stress-screen"
echo "  Room GPU ${ROOM_GPU}: docker logs -f k80-stress-room"
echo ""

# Wait for both stress tests to complete
SCREEN_EXIT=0
ROOM_EXIT=0

wait ${STRESS_SCREEN_PID} || SCREEN_EXIT=$?
wait ${STRESS_ROOM_PID} || ROOM_EXIT=$?

echo ""
echo "════════════════════════════════════════════════════════════"
echo "Burn-in Test Results"
echo "════════════════════════════════════════════════════════════"

if [ ${SCREEN_EXIT} -eq 0 ] && [ ${ROOM_EXIT} -eq 0 ]; then
  echo "✅ PASSED - Both GPUs completed stress test successfully"
  exit 0
else
  echo "❌ FAILED"
  [ ${SCREEN_EXIT} -ne 0 ] && echo "  Screen GPU (${SCREEN_GPU}): Exit code ${SCREEN_EXIT}"
  [ ${ROOM_EXIT} -ne 0 ] && echo "  Room GPU (${ROOM_GPU}): Exit code ${ROOM_EXIT}"
  exit 1
fi
