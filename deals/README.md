# Deals Module

A placeholder/stub module for fetching grocery deals and pricing information. This module provides an extensible provider architecture that allows different implementations to be plugged in.

## Structure

```
deals/
├── __init__.py
├── providers/
│   ├── __init__.py
│   ├── base.py         # Abstract base class
│   └── mock_ca.py      # Mock provider for Canadian stores
└── example_usage.py    # Usage example
```

## Usage

### Using the Mock Provider

```python
from deals.providers import MockCAProvider

# Create a provider instance
provider = MockCAProvider()

# Fetch deals
items = ["chicken breast", "sirloin steak"]
postal_code = "M5H 2N2"
result = provider.get_prices_for(items, postal_code)

# Access deals
for deal in result["deals"]:
    print(f"{deal['item']} at {deal['best_store']}: ${deal['unit_price']}/{deal['unit']}")
```

### Response Schema

The `get_prices_for` method returns a dictionary with the following structure:

```json
{
  "deals": [
    {
      "item": "sirloin steak",
      "best_store": "Metro",
      "unit_price": 12.99,
      "unit": "lb",
      "valid_to": "YYYY-MM-DD"
    }
  ]
}
```

## Creating a New Provider

To create a real provider implementation:

1. Create a new file in `deals/providers/` (e.g., `real_ca_provider.py`)
2. Import and inherit from `DealsProvider`
3. Implement the `get_prices_for` method
4. Add your provider to `deals/providers/__init__.py`

Example:

```python
from .base import DealsProvider
from typing import Dict, List

class RealCAProvider(DealsProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_prices_for(self, items: List[str], postal_code: str) -> Dict:
        # Implement real API call here
        pass
```

## Testing

Run the test suite:

```bash
python3 test_deals_providers.py
```

## Current Implementation

The `MockCAProvider` is a stub implementation that:
- Ignores input parameters
- Returns hardcoded deals data
- Provides realistic sample data for 5 grocery items
- Generates dynamic `valid_to` dates (7 days from now)

This allows the Deals agent to be developed and tested without requiring a real grocery deals API.
