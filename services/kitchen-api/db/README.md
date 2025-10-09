# Kitchen Stack Database Layer

This directory contains the database schema, migration scripts, and data access layer for the Kitchen Stack inventory management system.

## Files

- **schema.sql**: SQLite database schema defining tables for items, batches, price history, taste profiles, and weekly menu
- **migrate.py**: Migration script to initialize or update the database
- **data_access.py**: Data access layer providing Python functions for database operations

## Database Schema

### Tables

1. **items**: Master catalog of food items with nutritional data
2. **batches**: Individual batches of items with expiration tracking
3. **price_history**: Historical price tracking for items
4. **taste_profile**: User taste preferences and ratings
5. **weekly_menu**: Planned meals for the week

## Quick Start

### Initialize Database

```bash
# Initialize database (creates inventory.sqlite)
python3 db/migrate.py

# Or specify a custom path
python3 db/migrate.py /path/to/custom.sqlite
```

### Using the Data Access Layer

```python
from db import data_access

# Add an item
item_id = data_access.add_item({
    'name': 'Milk',
    'category': 'dairy',
    'unit': 'L',
    'calories_per_unit': 600.0,
    'protein_per_unit': 32.0
})

# Get an item
item = data_access.get_item(item_id)
print(item['name'])  # 'Milk'

# Add a batch
batch_id = data_access.add_batch({
    'item_id': item_id,
    'quantity': 2.0,
    'purchase_date': '2024-01-15',
    'expiration_date': '2024-01-22',
    'location': 'fridge',
    'cost': 5.99
})

# Update batch quantity
data_access.update_batch_quantity(batch_id, 1.5)

# Get expiring items (next 7 days)
expiring = data_access.get_expiring_items(7)
for item in expiring:
    print(f"{item['item_name']} expires on {item['expiration_date']}")
```

## API Reference

### Data Access Functions

#### `get_db_connection(db_path=None)`
Get a connection to the database.

#### `add_item(item_data)`
Add a new item to the inventory.
- **Required**: name, category, unit
- **Optional**: calories_per_unit, protein_per_unit, carbs_per_unit, fat_per_unit
- **Returns**: item_id

#### `get_item(item_id)`
Retrieve an item by ID.
- **Returns**: Dictionary with item data or None

#### `add_batch(batch_data)`
Add a new batch of an item.
- **Required**: item_id, quantity, purchase_date
- **Optional**: expiration_date, location, cost, notes
- **Returns**: batch_id

#### `get_batch(batch_id)`
Retrieve a batch by ID.
- **Returns**: Dictionary with batch data or None

#### `update_batch_quantity(batch_id, new_qty)`
Update the quantity of a batch.
- **Returns**: True if successful, False if batch not found

#### `get_all_items()`
Retrieve all items from the database.
- **Returns**: List of item dictionaries

#### `get_expiring_items(days_in_future=7)`
Get batches expiring within the specified number of days.
- **Returns**: List of batch dictionaries with item information

## Testing

Run the test suite:

```bash
pytest tests/test_data_access.py -v
```

## Environment Variables

- **DB_PATH**: Path to the SQLite database file (default: `inventory.sqlite`)

## Notes

- The migration script is idempotent and can be run multiple times safely
- Foreign keys are enabled to maintain referential integrity
- All timestamps use CURRENT_TIMESTAMP for automatic tracking
- The data access layer includes proper error handling and type hints
