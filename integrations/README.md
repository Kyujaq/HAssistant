# Home Assistant Integration Wrapper

This module provides a simple, reusable Python client to interact with the Home Assistant API.

## Overview

The `HAClient` class provides a clean interface for:
- Reading entity states
- Calling Home Assistant services
- Robust error handling and logging

## Installation

The client uses the `requests` library, which is already included in the project dependencies.

For testing:
```bash
pip install pytest requests-mock
```

## Usage

### Basic Setup

The client reads configuration from environment variables:

```bash
export HA_BASE_URL='http://homeassistant:8123'
export HA_TOKEN='your-long-lived-access-token'
```

### Example Code

```python
from integrations.ha_client import HAClient

# Initialize the client
client = HAClient()

# Get entity state
state = client.get_state('light.living_room')
if state:
    print(f"Light is {state['state']}")
    print(f"Brightness: {state['attributes'].get('brightness')}")

# Call a service
client.call_service(
    domain='light',
    service='turn_on',
    service_data={
        'entity_id': 'light.living_room',
        'brightness': 200
    }
)
```

### Complete Example

See `example_ha_client.py` for a complete working example.

## API Reference

### `HAClient()`

Initialize the Home Assistant client.

**Environment Variables:**
- `HA_BASE_URL`: Home Assistant base URL (e.g., `http://homeassistant:8123`)
- `HA_TOKEN`: Long-lived access token

**Raises:**
- `ValueError`: If required environment variables are not set

### `get_state(entity_id: str) -> Optional[Dict[str, Any]]`

Get the state of a Home Assistant entity.

**Parameters:**
- `entity_id`: The entity ID (e.g., `'light.living_room'`)

**Returns:**
- Dictionary containing the entity state object, or `None` if not found

**Raises:**
- `requests.exceptions.RequestException`: For network-related errors
- `ValueError`: For invalid responses or non-200 status codes (except 404)

**Example:**
```python
state = client.get_state('sun.sun')
print(f"Sun state: {state['state']}")  # 'above_horizon' or 'below_horizon'
```

### `call_service(domain: str, service: str, service_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`

Call a Home Assistant service.

**Parameters:**
- `domain`: The service domain (e.g., `'light'`, `'switch'`)
- `service`: The service name (e.g., `'turn_on'`, `'turn_off'`)
- `service_data`: Optional dictionary of service data/parameters

**Returns:**
- Dictionary containing the service call response

**Raises:**
- `requests.exceptions.RequestException`: For network-related errors
- `ValueError`: For invalid responses or non-200 status codes

**Example:**
```python
# Turn on a light with brightness
result = client.call_service(
    domain='light',
    service='turn_on',
    service_data={
        'entity_id': 'light.bedroom',
        'brightness': 150,
        'color_temp': 400
    }
)

# Call service without data
client.call_service('homeassistant', 'restart')
```

## Error Handling

The client provides comprehensive error handling:

- **Network Issues**: `requests.exceptions.ConnectionError`, `requests.exceptions.Timeout`
- **Authentication**: `ValueError` with HTTP 401 status
- **Not Found**: `get_state()` returns `None` for 404, `call_service()` raises `ValueError`
- **Server Errors**: `ValueError` with HTTP 5xx status

All API calls are logged using Python's `logging` module.

## Testing

Run the test suite:

```bash
pytest tests/test_ha_client.py -v
```

The tests use `requests-mock` to mock HTTP requests and verify:
- Initialization with/without environment variables
- Successful API calls
- Error handling for various failure scenarios
- Correct headers and payloads

## Integration with Existing Code

This client can be used throughout the project as a replacement for direct `requests` calls to the Home Assistant API. For example, the existing `pi_client.py` could be refactored to use this client for cleaner code organization.

## License

This module is part of the HAssistant project and follows the same license.
