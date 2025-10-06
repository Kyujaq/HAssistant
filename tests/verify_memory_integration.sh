#!/bin/bash
# Memory Integration Verification Script
# Verifies that all memory integration components are properly configured

set -e

echo "======================================"
echo "Memory Integration Verification"
echo "======================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0

check_passed() {
    echo -e "${GREEN}✓${NC} $1"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
}

check_failed() {
    echo -e "${RED}✗${NC} $1"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
}

check_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check 1: Docker Compose file exists
echo "Checking Docker Compose configuration..."
if [ -f "docker-compose.yml" ]; then
    check_passed "docker-compose.yml exists"
else
    check_failed "docker-compose.yml not found"
    exit 1
fi

# Check 2: Letta Bridge directory and files
echo ""
echo "Checking Letta Bridge service..."
if [ -d "services/letta-bridge" ]; then
    check_passed "services/letta-bridge directory exists"
    
    if [ -f "services/letta-bridge/main.py" ]; then
        check_passed "services/letta-bridge/main.py exists"
    else
        check_failed "services/letta-bridge/main.py not found"
    fi
    
    if [ -f "services/letta-bridge/Dockerfile" ]; then
        check_passed "services/letta-bridge/Dockerfile exists"
    else
        check_failed "services/letta-bridge/Dockerfile not found"
    fi
    
    if [ -f "services/letta-bridge/requirements.txt" ]; then
        check_passed "services/letta-bridge/requirements.txt exists"
    else
        check_failed "services/letta-bridge/requirements.txt not found"
    fi
else
    check_failed "services/letta-bridge directory not found"
fi

# Check 3: Database scripts
echo ""
echo "Checking database initialization scripts..."
if [ -d "scripts" ]; then
    check_passed "scripts directory exists"
    
    for script in "01_enable_pgvector.sql" "02_letta_schema.sql" "03_legacy_schema.sql" "04_indexes.sql"; do
        if [ -f "scripts/$script" ]; then
            check_passed "scripts/$script exists"
        else
            check_failed "scripts/$script not found"
        fi
    done
else
    check_failed "scripts directory not found"
fi

# Check 4: Environment configuration
echo ""
echo "Checking environment configuration..."
if [ -f "config/.env.example" ]; then
    check_passed "config/.env.example exists"
    
    # Check for key environment variables in config/.env.example
    required_vars=("POSTGRES_PASSWORD" "LETTA_PG_URI" "REDIS_PASSWORD" "LETTA_REDIS_URL" "BRIDGE_API_KEY")
    for var in "${required_vars[@]}"; do
        if grep -q "$var" config/.env.example; then
            check_passed "config/.env.example contains $var"
        else
            check_failed "config/.env.example missing $var"
        fi
    done
else
    check_failed "config/.env.example not found"
fi

if [ -f ".env" ]; then
    check_passed ".env file exists (ready for deployment)"
else
    check_warning ".env file not found (copy from config/.env.example for deployment)"
fi

# Check 5: Documentation
echo ""
echo "Checking documentation..."
if [ -f "docs/architecture/MEMORY_INTEGRATION.md" ]; then
    check_passed "docs/architecture/MEMORY_INTEGRATION.md exists"
else
    check_failed "docs/architecture/MEMORY_INTEGRATION.md not found"
fi

if [ -f "README.md" ]; then
    check_passed "README.md exists"
    
    if grep -q "Memory Integration" README.md; then
        check_passed "README.md contains Memory Integration section"
    else
        check_failed "README.md missing Memory Integration section"
    fi
else
    check_failed "README.md not found"
fi

# Check 6: Test script
echo ""
echo "Checking test infrastructure..."
if [ -f "tests/test_memory_integration.py" ]; then
    check_passed "tests/test_memory_integration.py exists"
    
    if [ -x "tests/test_memory_integration.py" ]; then
        check_passed "tests/test_memory_integration.py is executable"
    else
        check_warning "tests/test_memory_integration.py is not executable (chmod +x to fix)"
    fi
else
    check_failed "tests/test_memory_integration.py not found"
fi

# Check 7: Docker Compose services
echo ""
echo "Checking Docker Compose service definitions..."
services=("postgres" "redis" "letta-bridge")
for service in "${services[@]}"; do
    if grep -q "^  $service:" docker-compose.yml; then
        check_passed "Docker service '$service' defined"
    else
        check_failed "Docker service '$service' not found in docker-compose.yml"
    fi
done

# Check 8: Python dependencies in Letta Bridge
echo ""
echo "Checking Letta Bridge dependencies..."
if [ -f "services/letta-bridge/requirements.txt" ]; then
    required_deps=("fastapi" "uvicorn" "asyncpg" "redis" "numpy")
    for dep in "${required_deps[@]}"; do
        if grep -qi "$dep" services/letta-bridge/requirements.txt; then
            check_passed "Letta Bridge requires $dep"
        else
            check_failed "Letta Bridge missing $dep in requirements.txt"
        fi
    done
fi

# Check 9: Letta Bridge API endpoints
echo ""
echo "Checking Letta Bridge API endpoints..."
if [ -f "services/letta-bridge/main.py" ]; then
    endpoints=("/memory/add" "/memory/search" "/memory/pin" "/memory/forget" "/daily_brief" "/healthz")
    for endpoint in "${endpoints[@]}"; do
        if grep -q "$endpoint" services/letta-bridge/main.py; then
            check_passed "Endpoint $endpoint implemented"
        else
            check_failed "Endpoint $endpoint not found"
        fi
    done
fi

# Check 10: Healthchecks
echo ""
echo "Checking Docker healthchecks..."
if grep -q "healthcheck:" docker-compose.yml; then
    check_passed "Healthchecks defined in docker-compose.yml"
    
    # Check specific healthchecks
    if grep -A 5 "postgres:" docker-compose.yml | grep -q "healthcheck:"; then
        check_passed "PostgreSQL healthcheck configured"
    else
        check_warning "PostgreSQL healthcheck not found"
    fi
    
    if grep -A 5 "redis:" docker-compose.yml | grep -q "healthcheck:"; then
        check_passed "Redis healthcheck configured"
    else
        check_warning "Redis healthcheck not found"
    fi
    
    if grep -A 15 "letta-bridge:" docker-compose.yml | grep -q "healthcheck:"; then
        check_passed "Letta Bridge healthcheck configured"
    else
        check_warning "Letta Bridge healthcheck not found"
    fi
else
    check_warning "No healthchecks found in docker-compose.yml"
fi

# Summary
echo ""
echo "======================================"
echo "Verification Summary"
echo "======================================"
echo -e "Checks passed: ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Checks failed: ${RED}$CHECKS_FAILED${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Memory integration is properly configured.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Copy .env.example to .env and configure your settings"
    echo "2. Start services: docker compose up -d"
    echo "3. Check logs: docker compose logs letta-bridge postgres redis"
    echo "4. Run integration tests: python3 test_memory_integration.py"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please review the output above.${NC}"
    exit 1
fi
