#!/bin/bash
# Quick verification that K80 integration is ready

echo "======================================"
echo " K80 Integration Readiness Check"
echo "======================================"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

checks_passed=0
checks_total=0

# Check 1: nvidia-smi shows K80
checks_total=$((checks_total + 1))
echo -n "1. Checking if K80 is visible... "
if nvidia-smi | grep -q "Tesla K80"; then
    echo -e "${GREEN}✓ K80 detected${NC}"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗ K80 not found${NC}"
fi

# Check 2: vision-gateway container running
checks_total=$((checks_total + 1))
echo -n "2. Checking if vision-gateway is running... "
if docker ps | grep -q "vision-gateway"; then
    echo -e "${GREEN}✓ Container running${NC}"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗ Container not running${NC}"
fi

# Check 3: PyTorch can access K80
checks_total=$((checks_total + 1))
echo -n "3. Checking if PyTorch can access K80... "
k80_test=$(docker exec vision-gateway python3 -c "import torch; print(torch.cuda.get_device_name(2))" 2>&1)
if echo "$k80_test" | grep -q "K80"; then
    echo -e "${GREEN}✓ PyTorch can access K80${NC}"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗ PyTorch cannot access K80${NC}"
    echo "   Error: $k80_test"
fi

# Check 4: K80Preprocessor module imports
checks_total=$((checks_total + 1))
echo -n "4. Checking if K80Preprocessor imports... "
if docker exec vision-gateway python3 -c "from app.k80_preprocessor import K80Preprocessor, SceneTracker" 2>&1 | grep -q "imported successfully"; then
    echo -e "${GREEN}✓ Module imports successfully${NC}"
    checks_passed=$((checks_passed + 1))
elif docker exec vision-gateway python3 -c "from app.k80_preprocessor import K80Preprocessor, SceneTracker" 2>/dev/null; then
    echo -e "${GREEN}✓ Module imports successfully${NC}"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗ Module import failed${NC}"
fi

# Check 5: HDMI capture working
checks_total=$((checks_total + 1))
echo -n "5. Checking if HDMI capture is running... "
if docker logs vision-gateway 2>&1 | grep -q "Opened /dev/video2"; then
    echo -e "${GREEN}✓ HDMI capture active${NC}"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${YELLOW}⚠ HDMI capture not confirmed${NC}"
fi

# Check 6: Model weights status
checks_total=$((checks_total + 1))
echo -n "6. Checking if GroundingDINO model weights exist... "
if docker exec vision-gateway test -f /app/models/weights/groundingdino_swint_ogc.pth 2>/dev/null; then
    echo -e "${GREEN}✓ Model weights downloaded${NC}"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${YELLOW}⚠ Model weights not downloaded yet${NC}"
    echo "   Run: ./services/vision-gateway/download_models.sh"
fi

# Check 7: K80_ENABLED status
checks_total=$((checks_total + 1))
echo -n "7. Checking K80_ENABLED status... "
if docker exec vision-gateway printenv K80_ENABLED 2>/dev/null | grep -q "true"; then
    echo -e "${GREEN}✓ K80 enabled${NC}"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${YELLOW}⚠ K80 not enabled yet${NC}"
    echo "   Set K80_ENABLED=true in docker-compose.yml"
fi

echo ""
echo "======================================"
echo " Summary: $checks_passed/$checks_total checks passed"
echo "======================================"
echo ""

if [ "$checks_passed" -eq "$checks_total" ]; then
    echo -e "${GREEN}✓ All checks passed! K80 is fully operational!${NC}"
    echo ""
    echo "Monitor K80 detection logs:"
    echo "  docker compose logs -f vision-gateway | grep k80"
    exit 0
elif [ "$checks_passed" -ge 5 ]; then
    echo -e "${YELLOW}⚠ K80 integration is ready, but needs activation:${NC}"
    echo ""
    echo "To enable K80 detection:"
    echo "  1. ./services/vision-gateway/download_models.sh"
    echo "  2. Edit docker-compose.yml: Set K80_ENABLED=true"
    echo "  3. docker compose restart vision-gateway"
    echo ""
    echo "See: K80_QUICK_START.md"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Review the output above.${NC}"
    exit 1
fi
