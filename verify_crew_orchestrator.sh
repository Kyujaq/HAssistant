#!/bin/bash
# Verification script for crew-orchestrator service
# Checks code quality, structure, and configuration

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CREW_DIR="$SCRIPT_DIR/crew-orchestrator"

passed=0
failed=0
warnings=0

check_passed() {
    echo -e "${GREEN}✓${NC} $1"
    passed=$((passed + 1))
}

check_failed() {
    echo -e "${RED}✗${NC} $1"
    failed=$((failed + 1))
}

check_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    warnings=$((warnings + 1))
}

echo "========================================"
echo "Crew Orchestrator Verification Script"
echo "========================================"
echo ""

# Check 1: Directory structure
echo "Checking directory structure..."
if [ -d "$CREW_DIR" ]; then
    check_passed "crew-orchestrator directory exists"
else
    check_failed "crew-orchestrator directory not found"
    exit 1
fi

# Check 2: Required files
echo ""
echo "Checking required files..."
required_files=("main.py" "crew_tools.py" "requirements.txt" "Dockerfile" "README.md")
for file in "${required_files[@]}"; do
    if [ -f "$CREW_DIR/$file" ]; then
        check_passed "$file exists"
    else
        check_failed "$file not found"
    fi
done

# Check 3: Python syntax
echo ""
echo "Checking Python syntax..."
if command -v python3 &> /dev/null; then
    if python3 -m py_compile "$CREW_DIR/main.py" 2>/dev/null; then
        check_passed "main.py syntax valid"
    else
        check_failed "main.py has syntax errors"
    fi
    
    if python3 -m py_compile "$CREW_DIR/crew_tools.py" 2>/dev/null; then
        check_passed "crew_tools.py syntax valid"
    else
        check_failed "crew_tools.py has syntax errors"
    fi
else
    check_warning "python3 not found, skipping syntax checks"
fi

# Check 4: No duplicate code patterns
echo ""
echo "Checking for duplicate code patterns..."
if ! grep -q "class KickoffPayload" "$CREW_DIR/main.py"; then
    check_passed "No obsolete KickoffPayload class found"
else
    check_failed "Found obsolete KickoffPayload class (should use CrewTask)"
fi

if ! grep -q "def read_root" "$CREW_DIR/main.py"; then
    check_passed "No obsolete read_root function found"
else
    check_failed "Found obsolete read_root function (should use root)"
fi

if ! grep -q "def speak_command_to_windows" "$CREW_DIR/crew_tools.py"; then
    check_passed "No obsolete speak_command_to_windows function found"
else
    check_failed "Found obsolete speak_command_to_windows function"
fi

# Check 5: Port configuration
echo ""
echo "Checking port configuration..."
if grep -q "PORT=8084" "$CREW_DIR/Dockerfile"; then
    check_passed "Dockerfile PORT set correctly to 8084"
else
    check_failed "Dockerfile PORT not set to 8084"
fi

if grep -q "EXPOSE 8084" "$CREW_DIR/Dockerfile"; then
    check_passed "Dockerfile EXPOSE set correctly to 8084"
else
    check_failed "Dockerfile EXPOSE not set to 8084"
fi

if grep -q "port=8084" "$CREW_DIR/main.py"; then
    check_passed "main.py default port set to 8084"
else
    check_failed "main.py default port not set to 8084"
fi

# Check 6: Input validation
echo ""
echo "Checking input validation..."
if grep -q "@validator" "$CREW_DIR/main.py"; then
    check_passed "Input validators present in main.py"
else
    check_warning "No input validators found in main.py"
fi

if grep -q "@validator" "$CREW_DIR/crew_tools.py"; then
    check_passed "Input validators present in crew_tools.py"
else
    check_warning "No input validators found in crew_tools.py"
fi

# Check 7: Error handling
echo ""
echo "Checking error handling..."
if grep -q "try:" "$CREW_DIR/main.py" && grep -q "except" "$CREW_DIR/main.py"; then
    check_passed "Error handling present in main.py"
else
    check_warning "Limited error handling in main.py"
fi

if grep -q "try:" "$CREW_DIR/crew_tools.py" && grep -q "except" "$CREW_DIR/crew_tools.py"; then
    check_passed "Error handling present in crew_tools.py"
else
    check_warning "Limited error handling in crew_tools.py"
fi

# Check 8: Logging
echo ""
echo "Checking logging..."
if grep -q "logger = logging.getLogger" "$CREW_DIR/main.py"; then
    check_passed "Logger configured in main.py"
else
    check_warning "No logger found in main.py"
fi

if grep -q "logger = logging.getLogger" "$CREW_DIR/crew_tools.py"; then
    check_passed "Logger configured in crew_tools.py"
else
    check_warning "No logger found in crew_tools.py"
fi

# Check 9: Docker configuration
echo ""
echo "Checking Docker configuration..."
if [ -f "docker-compose.yml" ]; then
    if grep -q "crew-orchestrator:" docker-compose.yml; then
        check_passed "Service defined in docker-compose.yml"
        
        if grep -q "8084:8084" docker-compose.yml; then
            check_passed "Port mapping correct in docker-compose.yml"
        else
            check_failed "Port mapping incorrect in docker-compose.yml"
        fi
    else
        check_failed "Service not found in docker-compose.yml"
    fi
else
    check_warning "docker-compose.yml not found in root"
fi

# Check 10: Documentation
echo ""
echo "Checking documentation..."
if [ -f "$CREW_DIR/README.md" ]; then
    if grep -q "API Endpoints" "$CREW_DIR/README.md"; then
        check_passed "README includes API documentation"
    else
        check_warning "README missing API documentation"
    fi
    
    if grep -q "Environment Variables" "$CREW_DIR/README.md"; then
        check_passed "README includes environment variables"
    else
        check_warning "README missing environment variables"
    fi
else
    check_failed "README.md not found"
fi

# Check 11: Dependencies
echo ""
echo "Checking dependencies..."
required_deps=("fastapi" "uvicorn" "crewai" "crewai-tools" "pydantic")
for dep in "${required_deps[@]}"; do
    if grep -qi "^$dep" "$CREW_DIR/requirements.txt"; then
        check_passed "Dependency $dep present"
    else
        check_failed "Dependency $dep missing"
    fi
done

# Check 12: Test file exists
echo ""
echo "Checking test infrastructure..."
if [ -f "test_crew_orchestrator.py" ]; then
    check_passed "Test file exists"
    
    if [ -x "test_crew_orchestrator.py" ]; then
        check_passed "Test file is executable"
    else
        check_warning "Test file not executable (chmod +x to fix)"
    fi
else
    check_warning "No test file found"
fi

# Summary
echo ""
echo "========================================"
echo "Verification Results:"
echo "  ${GREEN}Passed:${NC} $passed"
echo "  ${RED}Failed:${NC} $failed"
echo "  ${YELLOW}Warnings:${NC} $warnings"
echo "========================================"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please review above.${NC}"
    exit 1
fi
