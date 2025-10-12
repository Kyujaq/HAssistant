#!/bin/bash
# Download GroundingDINO model weights for K80 GPU preprocessing

set -e

echo "======================================"
echo " GroundingDINO Model Download Script"
echo "======================================"

CONTAINER_NAME="vision-gateway"
MODEL_DIR="/app/models"

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "ERROR: Container '$CONTAINER_NAME' is not running"
    echo "Please start the container first with: docker compose up -d vision-gateway"
    exit 1
fi

echo ""
echo "Creating model directory..."
docker exec "$CONTAINER_NAME" mkdir -p "$MODEL_DIR/weights"
docker exec "$CONTAINER_NAME" mkdir -p "$MODEL_DIR/GroundingDINO"

echo ""
echo "Downloading GroundingDINO model weights (~700MB)..."
docker exec "$CONTAINER_NAME" bash -c "cd $MODEL_DIR/weights && wget -q --show-progress https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth || echo 'Download failed'"

echo ""
echo "Downloading GroundingDINO config..."
docker exec "$CONTAINER_NAME" bash -c "cd $MODEL_DIR && git clone --depth 1 https://github.com/IDEA-Research/GroundingDINO.git || echo 'Clone failed'"

echo ""
echo "Verifying downloads..."
if docker exec "$CONTAINER_NAME" test -f "$MODEL_DIR/weights/groundingdino_swint_ogc.pth"; then
    echo "✓ Model weights downloaded successfully"
else
    echo "✗ Model weights not found - download may have failed"
    exit 1
fi

if docker exec "$CONTAINER_NAME" test -f "$MODEL_DIR/GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py"; then
    echo "✓ Config file downloaded successfully"
else
    echo "✗ Config file not found - download may have failed"
    exit 1
fi

echo ""
echo "======================================"
echo " Download Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Update docker-compose.yml: Set K80_ENABLED=true"
echo "2. Restart vision-gateway: docker compose restart vision-gateway"
echo "3. Check logs: docker compose logs -f vision-gateway"
echo ""
echo "The K80 will now perform continuous object detection at ~5-10 FPS"
echo "and only call the heavy Qwen VL model when scenes change significantly."
echo ""
