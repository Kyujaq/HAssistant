#!/bin/bash

# GPU 3 Real-World Vision Gateway - Verification Script
# Run this before starting the service to verify everything is ready

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GPU 3 Real-World Vision Gateway - Pre-Flight Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Check 1: Service files exist
echo "✓ Checking service files..."
if [ ! -f "services/realworld-gateway/Dockerfile" ]; then
    echo "❌ ERROR: Dockerfile missing"
    exit 1
fi
if [ ! -f "services/realworld-gateway/app/main.py" ]; then
    echo "❌ ERROR: main.py missing"
    exit 1
fi
if [ ! -f "services/realworld-gateway/app/k80_realworld_processor.py" ]; then
    echo "❌ ERROR: k80_realworld_processor.py missing"
    exit 1
fi
echo "  ✓ All service files present"
echo

# Check 2: Docker Compose configuration
echo "✓ Checking docker-compose.yml..."
if ! grep -q "realworld-gateway:" docker-compose.yml; then
    echo "❌ ERROR: realworld-gateway not found in docker-compose.yml"
    exit 1
fi
if ! grep -q "device_ids: \['3'\]" docker-compose.yml; then
    echo "⚠️  WARNING: GPU 3 device_ids not found (expected: device_ids: ['3'])"
fi
echo "  ✓ Docker Compose configuration found"
echo

# Check 3: GPU availability
echo "✓ Checking GPU availability..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ ERROR: nvidia-smi not found - NVIDIA drivers not installed?"
    exit 1
fi

GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
echo "  Found $GPU_COUNT GPUs:"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader | nl -v 0

if [ "$GPU_COUNT" -lt 4 ]; then
    echo "⚠️  WARNING: Expected 4 GPUs, found $GPU_COUNT"
    echo "  GPU 3 may not be available!"
fi
echo

# Check 4: Webcam availability
echo "✓ Checking webcam availability..."
if [ ! -c "/dev/video0" ]; then
    echo "❌ ERROR: /dev/video0 not found"
    echo "  Connect webcam or update WEBCAM_DEVICE in docker-compose.yml"
    exit 1
fi
echo "  ✓ /dev/video0 found"

# List all video devices
echo "  Available video devices:"
ls -la /dev/video* 2>/dev/null || echo "  (none found)"
echo

# Check 5: Environment variables
echo "✓ Checking environment variables..."
if [ ! -f ".env" ]; then
    echo "⚠️  WARNING: .env file not found"
    echo "  Copy from config/.env.example if needed"
else
    if ! grep -q "HA_TOKEN" .env; then
        echo "⚠️  WARNING: HA_TOKEN not set in .env"
    fi
    if ! grep -q "COMPREFACE_API_KEY" .env; then
        echo "  ℹ️  COMPREFACE_API_KEY not set (optional)"
    fi
fi
echo

# Check 6: Home Assistant camera config
echo "✓ Checking Home Assistant camera config..."
if [ ! -f "ha_config/glados_vision_cameras.yaml" ]; then
    echo "⚠️  WARNING: ha_config/glados_vision_cameras.yaml not found"
    echo "  Create this file to enable HA camera integration"
else
    echo "  ✓ Camera config file present"
    echo "  Remember to add to HA configuration.yaml:"
    echo "    camera: !include glados_vision_cameras.yaml"
fi
echo

# Check 7: Documentation
echo "✓ Checking documentation..."
if [ ! -f "REALWORLD_VISION_QUICK_START.md" ]; then
    echo "⚠️  WARNING: Quick start guide missing"
else
    echo "  ✓ Quick start guide present"
fi
if [ ! -f "docs/implementation/GPU3_REALWORLD_VISION_COMPLETE.md" ]; then
    echo "⚠️  WARNING: Full documentation missing"
else
    echo "  ✓ Full documentation present"
fi
echo

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pre-Flight Check Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "Ready to build and start realworld-gateway!"
echo
echo "Next steps:"
echo "  1. Build:  docker compose build realworld-gateway"
echo "  2. Start:  docker compose up -d realworld-gateway"
echo "  3. Logs:   docker compose logs -f realworld-gateway"
echo "  4. Test:   curl http://localhost:8089/healthz"
echo
echo "See REALWORLD_VISION_QUICK_START.md for full instructions."
echo
