# Tests

This directory contains test files for HAssistant services and components.

## Test Files

### test_memory_integration.py
**Purpose**: Tests the Letta Bridge memory API endpoints

**Coverage**:
- Health check endpoint
- Memory add endpoint
- Memory search endpoint
- Memory pin endpoint
- Memory forget endpoint
- Daily brief endpoint

**Running**:
```bash
# Install dependencies
pip install httpx pytest

# Start services
docker compose up -d letta-bridge postgres redis

# Run tests
python3 tests/test_memory_integration.py
```

---

### test_computer_control_agent.py
**Purpose**: Unit tests for computer control agent

**Coverage**:
- Agent initialization
- Screen info retrieval
- Screenshot capture
- OCR functionality
- Element detection
- Safety checks

**Running**:
```bash
# Install dependencies
pip install -r config/computer_control_requirements.txt
pip install pytest

# Run tests
python3 tests/test_computer_control_agent.py
```

---

### test_windows_voice_control.py
**Purpose**: Tests for Windows Voice control bridge

**Coverage**:
- Command sanitization
- Audio routing
- TTS integration
- Safety validations

**Running**:
```bash
python3 tests/test_windows_voice_control.py
```

---

### test_windows_voice_integration.py
**Purpose**: Integration tests for computer control + Windows Voice

**Coverage**:
- Agent initialization in different modes
- Mode switching (direct vs Windows Voice)
- Command execution through voice bridge
- Integration points

**Running**:
```bash
python3 tests/test_windows_voice_integration.py
```

---

## Shell Scripts

### verify_memory_integration.sh
**Purpose**: Comprehensive verification of memory integration setup

**Checks**:
- Docker compose configuration
- Service directories and files
- Database initialization scripts
- Environment configuration
- Documentation
- Test infrastructure
- Python dependencies
- API endpoints (if services running)

**Running**:
```bash
bash tests/verify_memory_integration.sh
```

**Output**:
- ✅ Passed checks
- ⚠️  Warnings
- ❌ Failed checks

---

### test_windows_clarity.sh
**Purpose**: Tests Windows Voice clarity configurations

**Checks**:
- Voice model availability
- Audio device configuration
- TTS output quality
- Recognition accuracy

**Running**:
```bash
bash tests/test_windows_clarity.sh
```

---

## Running All Tests

### Quick Test
```bash
# Run all Python tests
python3 -m pytest tests/

# Run verification scripts
bash tests/verify_memory_integration.sh
bash tests/test_windows_clarity.sh
```

### Comprehensive Test Suite

```bash
#!/bin/bash
set -e

echo "Starting HAssistant Test Suite..."

# Start services
echo "Starting services..."
docker compose up -d
sleep 10

# Verify memory integration
echo "=== Memory Integration Verification ==="
bash tests/verify_memory_integration.sh

# Run Python tests
echo "=== Python Unit Tests ==="
python3 tests/test_memory_integration.py
python3 tests/test_computer_control_agent.py
python3 tests/test_windows_voice_control.py
python3 tests/test_windows_voice_integration.py

# Run clarity tests
echo "=== Windows Voice Clarity Tests ==="
bash tests/test_windows_clarity.sh

echo "All tests completed!"
```

---

## Test Requirements

### Python Dependencies
```bash
pip install pytest httpx requests flask pyautogui pytesseract pillow opencv-python numpy
```

### System Requirements
- Docker and Docker Compose
- Python 3.8+
- Tesseract OCR (for computer control tests)
- Audio device (for Windows Voice tests)

---

## Writing New Tests

### Python Test Template

```python
#!/usr/bin/env python3
"""
Tests for [Component Name]
"""

import unittest
import sys
import os

# Add necessary paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'clients'))

class TestComponent(unittest.TestCase):
    """Test suite for [Component]"""
    
    def setUp(self):
        """Set up test fixtures"""
        pass
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_basic_functionality(self):
        """Test basic functionality"""
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
```

### Shell Script Template

```bash
#!/bin/bash
# Tests for [Component Name]

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

check_passed() {
    echo -e "${GREEN}✓${NC} $1"
}

check_failed() {
    echo -e "${RED}✗${NC} $1"
}

check_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Your test logic here
echo "Running tests..."
```

---

## Continuous Integration

### GitHub Actions (Example)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install pytest httpx requests
    
    - name: Start services
      run: docker compose up -d
    
    - name: Run tests
      run: |
        python3 -m pytest tests/
        bash tests/verify_memory_integration.sh
```

---

## Test Coverage

Current test coverage by component:

| Component | Tests | Coverage |
|-----------|-------|----------|
| Memory API | ✅ | Basic endpoints |
| Computer Control | ✅ | Unit tests |
| Windows Voice | ✅ | Unit + integration |
| GLaDOS Orchestrator | ⚠️  | Manual testing |
| Vision Gateway | ⚠️  | Manual testing |
| Qwen Agent | ⚠️  | Basic tests |

**Legend**:
- ✅ Good coverage
- ⚠️  Partial coverage
- ❌ No coverage

---

## See Also

- [TESTING_ROADMAP.md](../docs/TESTING_ROADMAP.md) - Overall testing strategy
- [Services README](../services/README.md) - Service documentation
- [Examples](../examples/README.md) - Example usage patterns
