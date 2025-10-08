#!/usr/bin/env bash
#
# Auto-discover Tesla K80 GPUs and set environment variables
#
set -euo pipefail

echo "🔍 Detecting Tesla K80 GPUs..."

# Query all GPUs and filter for K80
K80_INDICES=$(nvidia-smi --query-gpu=index,name --format=csv,noheader | grep -i "K80" | awk -F',' '{print $1}' | tr -d ' ')

if [ -z "$K80_INDICES" ]; then
    echo "⚠️  No Tesla K80 GPUs detected"
    echo ""
    echo "Available GPUs:"
    nvidia-smi --query-gpu=index,name --format=csv
    exit 1
fi

# Convert to array
K80_ARRAY=($K80_INDICES)
K80_COUNT=${#K80_ARRAY[@]}

echo "✅ Found ${K80_COUNT} K80 GPU(s):"
for idx in "${K80_ARRAY[@]}"; do
    GPU_INFO=$(nvidia-smi --id=$idx --query-gpu=name,memory.total,compute_cap --format=csv,noheader)
    echo "  GPU $idx: $GPU_INFO"
done

echo ""

# Assign GPUs
if [ ${K80_COUNT} -ge 2 ]; then
    SCREEN_GPU=${K80_ARRAY[0]}
    ROOM_GPU=${K80_ARRAY[1]}
    echo "📺 Screen worker → GPU ${SCREEN_GPU}"
    echo "📹 Room worker   → GPU ${ROOM_GPU}"
elif [ ${K80_COUNT} -eq 1 ]; then
    SCREEN_GPU=${K80_ARRAY[0]}
    ROOM_GPU=${K80_ARRAY[0]}
    echo "⚠️  Only one K80 found. Both workers will share GPU ${SCREEN_GPU}"
else
    echo "❌ No K80 GPUs found"
    exit 1
fi

# Export for docker-compose
export VISION_SCREEN_CUDA_DEVICE=${SCREEN_GPU}
export VISION_ROOM_CUDA_DEVICE=${ROOM_GPU}

echo ""
echo "Environment variables set:"
echo "  VISION_SCREEN_CUDA_DEVICE=${VISION_SCREEN_CUDA_DEVICE}"
echo "  VISION_ROOM_CUDA_DEVICE=${VISION_ROOM_CUDA_DEVICE}"
echo ""
echo "To use these values with docker-compose:"
echo "  export VISION_SCREEN_CUDA_DEVICE=${VISION_SCREEN_CUDA_DEVICE}"
echo "  export VISION_ROOM_CUDA_DEVICE=${VISION_ROOM_CUDA_DEVICE}"
echo "  docker compose up -d vision-screen vision-room"
