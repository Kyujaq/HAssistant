# Example Scripts

This directory contains example scripts demonstrating how to use HAssistant services and clients.

## Available Examples

### example_memory_client.py
**Purpose**: Demonstrates how to interact with the Letta Bridge memory API

**Features**:
- Adding memories
- Searching memories
- Pinning important memories
- Retrieving daily briefs
- Memory maintenance

**Usage**:
```bash
# Make sure services are running
docker compose up -d

# Run the example
python3 examples/example_memory_client.py
```

**Key API Calls Demonstrated**:
```python
# Add a memory
POST http://localhost:8081/memory/add
{
  "type": "fact",
  "title": "User preference",
  "content": "User prefers concise responses",
  "tier": "long"
}

# Search memories
GET http://localhost:8081/memory/search?q=user+preferences&k=5

# Get daily brief
GET http://localhost:8081/daily_brief
```

---

### example_computer_control.py
**Purpose**: Demonstrates computer control agent capabilities

**Features**:
- Getting screen information
- Taking screenshots
- Finding elements on screen
- Clicking on UI elements
- Typing text
- Running automated tasks

**Setup**:
```bash
# Install dependencies
pip install -r config/computer_control_requirements.txt

# Configure agent
cp config/computer_control_agent.env.example computer_control_agent.env
nano computer_control_agent.env

# Run examples
python3 examples/example_computer_control.py
```

**Examples Included**:
1. Get screen info (resolution, current application)
2. Take and analyze screenshots
3. Find specific UI elements
4. Automated workflows (e.g., Excel manipulation)
5. Browser automation

---

### example_integration.py
**Purpose**: Shows how to integrate HAssistant services into your own applications

**Features**:
- Connecting to Ollama for LLM inference
- Using GLaDOS Orchestrator for query routing
- Integrating memory retrieval
- Combining multiple services

**Usage**:
```bash
# Make sure services are running
docker compose up -d

# Run the integration example
python3 examples/example_integration.py
```

**Integration Patterns Shown**:
- Direct Ollama API calls
- Using the orchestrator for smart routing
- Memory-aware conversations
- Error handling and retries
- Streaming responses

---

## Running All Examples

To run all examples in sequence:

```bash
# Ensure all services are running
docker compose up -d

# Wait for services to be healthy
sleep 10

# Run memory example
echo "=== Memory Integration Example ==="
python3 examples/example_memory_client.py

# Run computer control example (requires GUI)
if [ -n "$DISPLAY" ]; then
    echo "=== Computer Control Example ==="
    python3 examples/example_computer_control.py
fi

# Run integration example
echo "=== Service Integration Example ==="
python3 examples/example_integration.py
```

---

## Creating Your Own Examples

When creating new examples:

1. **Add proper documentation** at the top of the file
2. **Include usage instructions** in docstrings
3. **Handle errors gracefully** with try/catch blocks
4. **Check dependencies** before running
5. **Use configuration files** from `config/` directory
6. **Add your example to this README**

Example template:

```python
#!/usr/bin/env python3
"""
Example: [Brief description]

This example demonstrates:
- Feature 1
- Feature 2

Requirements:
- Service X must be running
- Install: pip install dependency1 dependency2

Usage:
    python3 examples/your_example.py
"""

import sys
import os

# Add necessary paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'clients'))

def main():
    """Main example logic"""
    print("Example output...")
    
if __name__ == "__main__":
    main()
```

---

## Troubleshooting

**Problem**: Import errors  
**Solution**: Make sure you're running from the repository root or adjust Python path

**Problem**: Connection refused  
**Solution**: Ensure docker compose services are running: `docker compose ps`

**Problem**: Authentication errors  
**Solution**: Check `.env` file has correct API keys and tokens

**Problem**: GUI examples fail  
**Solution**: Make sure you have a display (X11) available and necessary packages installed

---

## See Also

- [Client Scripts](../clients/README.md) - Production-ready client scripts
- [Service Documentation](../services/README.md) - Service APIs and usage
- [Main README](../README.md) - Overall setup and configuration
