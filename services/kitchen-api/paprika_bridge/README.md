# Paprika Bridge

Python client for interacting with the Paprika V2 API via the Kappari reverse-engineered endpoint.

## Features

- **Authentication**: Automatic login and session token management
- **Retry Logic**: Exponential backoff for HTTP 429 (Too Many Requests) and 5xx server errors
- **Recipe Management**: Fetch all recipes from your Paprika account
- **Meal Planning**: Get and post meals to your calendar
- **Grocery Lists**: Retrieve and add items to your grocery list
- **Normalized Responses**: All methods return Python dictionaries matching project schemas

## Installation

The client requires Python 3.8+ and the `requests` library:

```bash
pip install requests
```

## Usage

### Basic Example

```python
from paprika_bridge import KappariClient

# Initialize client
client = KappariClient()

# Authenticate
client.login(email="your_email@example.com", password="your_password")

# Get recipes
recipes = client.get_recipes()
print(f"Found {len(recipes)} recipes")

# Get grocery list
grocery_list = client.get_grocery_list()
items = grocery_list.get("items", [])
print(f"Grocery list has {len(items)} items")
```

### Environment Variables

For convenience, you can set credentials as environment variables:

```bash
export PAPRIKA_EMAIL="your_email@example.com"
export PAPRIKA_PASSWORD="your_password"
```

Then use them in your code:

```python
import os
from paprika_bridge import KappariClient

client = KappariClient()
client.login(
    email=os.getenv("PAPRIKA_EMAIL"),
    password=os.getenv("PAPRIKA_PASSWORD")
)
```

### Available Methods

#### `login(email, password)`
Authenticate with the Paprika API and obtain a session token.

```python
result = client.login(email="user@example.com", password="password")
```

#### `get_recipes()`
Get all recipes from your Paprika account.

```python
recipes = client.get_recipes()
for recipe in recipes:
    print(recipe.get("name"))
```

#### `get_meals(start_date, end_date)`
Get meals within a date range.

```python
meals = client.get_meals("2025-01-01", "2025-01-31")
for meal in meals:
    print(f"{meal['date']} - {meal['type']}: {meal['recipe_name']}")
```

#### `get_grocery_list()`
Get the current grocery list.

```python
grocery_list = client.get_grocery_list()
items = grocery_list.get("items", [])
for item in items:
    print(f"- {item['name']} ({item['quantity']})")
```

#### `add_grocery_item(name, quantity=None, note=None)`
Add an item to the grocery list.

```python
client.add_grocery_item("Milk", quantity="1 gallon", note="Organic")
```

#### `post_meal(date, meal_type, recipe_id)`
Add a meal to the calendar.

```python
client.post_meal(
    date="2025-01-15",
    meal_type="dinner",
    recipe_id="recipe-uuid-here"
)
```

#### `healthcheck()`
Check if the client is properly authenticated and can reach the API.

```python
if client.healthcheck():
    print("Client is healthy")
```

## Retry Logic

The client implements exponential backoff retry logic for handling:
- HTTP 429 (Too Many Requests)
- HTTP 5xx (Server Errors)

Configuration:
- **Max Retries**: 5 attempts
- **Backoff Factor**: Starts at 1 second, doubles each retry
- **Retry Schedule**: 1s, 2s, 4s, 8s, 16s

Example wait times:
- Attempt 1: 1 second
- Attempt 2: 2 seconds
- Attempt 3: 4 seconds
- Attempt 4: 8 seconds
- Attempt 5: 16 seconds

## Testing

### Smoke Test

A smoke test script is provided to verify connectivity:

```bash
export PAPRIKA_EMAIL="your_email@example.com"
export PAPRIKA_PASSWORD="your_password"
python3 tests/smoke_test_kappari.py
```

The smoke test will:
1. Initialize the client
2. Authenticate with the API
3. Fetch recipes and print count
4. Fetch grocery list and print count
5. Run a healthcheck

### Running the Client Directly

You can also run the client module directly:

```bash
export PAPRIKA_EMAIL="your_email@example.com"
export PAPRIKA_PASSWORD="your_password"
python3 -m paprika_bridge.kappari_client
```

## API Endpoint

The client uses the Paprika V2 API endpoint:
- Base URL: `https://www.paprikaapp.com/api/v2`

This is the reverse-engineered Kappari endpoint.

## Error Handling

The client raises `requests.exceptions.RequestException` for API errors. Always wrap API calls in try-except blocks:

```python
try:
    recipes = client.get_recipes()
except requests.exceptions.RequestException as e:
    print(f"API error: {e}")
```

## Security Notes

- Never commit credentials to source control
- Use environment variables for sensitive data
- Store credentials securely (e.g., in a secrets manager)
- The session token is stored in memory only

## License

MIT License - see main project LICENSE file for details.
