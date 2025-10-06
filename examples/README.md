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

### example_ha_client.py
**Purpose**: Demonstrates how to use the Home Assistant integration wrapper

**Features**:
- Getting entity states
- Calling HA services
- Error handling
- Environment variable configuration

**Usage**:
```bash
# Set environment variables
export HA_BASE_URL='http://homeassistant:8123'
export HA_TOKEN='your-long-lived-access-token'

# Run the example
python3 examples/example_ha_client.py
```

---

### example_kitchen_stack.py
**Purpose**: Demonstrates the kitchen stack orchestrator and data access

**Features**:
- Database access patterns
- Data migration
- Orchestrator usage

**Usage**:
```bash
# Make sure database is running
docker compose up -d postgres

# Run the example
python3 examples/example_kitchen_stack.py
```

---

### example_vision_intake.py
**Purpose**: Demonstrates vision intake API usage

**Features**:
- Vision API integration
- Image processing
- OCR capabilities

**Usage**:
```bash
# Make sure vision-gateway is running
docker compose up -d vision-gateway

# Run the example
python3 examples/example_vision_intake.py
```

---

## General Usage

All examples assume services are running:

```bash
# Start services
docker compose up -d

# Run an example
python3 examples/example_*.py
```

## See Also

- [Services Documentation](../services/README.md) - Service details
- [API Documentation](../docs/architecture/) - API references
- [Main README](../README.md) - Overall project documentation
