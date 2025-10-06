#!/usr/bin/env python3
"""
Example usage of the Kitchen Stack Database Layer
Demonstrates the complete workflow from database initialization to querying.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from db import data_access
from db.migrate import migrate


def main():
    """Run example workflow."""
    print("=" * 60)
    print("Kitchen Stack Database - Example Workflow")
    print("=" * 60)
    
    # Set up database path
    db_path = "example_inventory.sqlite"
    os.environ["DB_PATH"] = db_path
    
    # Step 1: Initialize database
    print("\n1. Initializing database...")
    schema_path = Path(__file__).parent / "db" / "schema.sql"
    if not migrate(db_path, schema_path):
        print("Failed to initialize database!")
        sys.exit(1)
    
    # Step 2: Add items
    print("\n2. Adding items to inventory...")
    items = [
        {
            'name': 'Whole Milk',
            'category': 'dairy',
            'unit': 'L',
            'calories_per_unit': 600.0,
            'protein_per_unit': 32.0,
            'carbs_per_unit': 48.0,
            'fat_per_unit': 32.0
        },
        {
            'name': 'Bananas',
            'category': 'produce',
            'unit': 'kg',
            'calories_per_unit': 890.0,
            'protein_per_unit': 11.0,
            'carbs_per_unit': 229.0,
            'fat_per_unit': 3.3
        },
        {
            'name': 'Chicken Breast',
            'category': 'meat',
            'unit': 'kg',
            'calories_per_unit': 1650.0,
            'protein_per_unit': 310.0,
            'carbs_per_unit': 0.0,
            'fat_per_unit': 36.0
        }
    ]
    
    item_ids = {}
    for item in items:
        item_id = data_access.add_item(item)
        item_ids[item['name']] = item_id
        print(f"  ✓ Added: {item['name']} (ID: {item_id})")
    
    # Step 3: Add batches
    print("\n3. Adding batches with expiration dates...")
    today = datetime.now().strftime('%Y-%m-%d')
    
    batches = [
        {
            'item_id': item_ids['Whole Milk'],
            'quantity': 2.0,
            'purchase_date': today,
            'expiration_date': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'location': 'fridge',
            'cost': 5.99,
            'notes': 'Organic, local farm'
        },
        {
            'item_id': item_ids['Bananas'],
            'quantity': 1.5,
            'purchase_date': today,
            'expiration_date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
            'location': 'counter',
            'cost': 2.49
        },
        {
            'item_id': item_ids['Chicken Breast'],
            'quantity': 0.8,
            'purchase_date': today,
            'expiration_date': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'location': 'fridge',
            'cost': 12.99,
            'notes': 'Free range'
        }
    ]
    
    batch_ids = []
    for batch in batches:
        batch_id = data_access.add_batch(batch)
        batch_ids.append(batch_id)
        item = data_access.get_item(batch['item_id'])
        print(f"  ✓ Added batch: {item['name']}, {batch['quantity']} {item['unit']}, expires: {batch['expiration_date']}")
    
    # Step 4: Get all items
    print("\n4. Listing all items in inventory...")
    all_items = data_access.get_all_items()
    for item in all_items:
        print(f"  - {item['name']} ({item['category']}): {item['calories_per_unit']:.1f} cal/{item['unit']}")
    
    # Step 5: Check expiring items
    print("\n5. Checking items expiring in next 7 days...")
    expiring = data_access.get_expiring_items(7)
    if expiring:
        for item in expiring:
            print(f"  ⚠ {item['item_name']}: {item['quantity']} {item['item_unit']} expires on {item['expiration_date']}")
            print(f"     Location: {item['location']}")
    else:
        print("  ✓ No items expiring soon!")
    
    # Step 6: Update batch quantity (simulate consumption)
    print("\n6. Updating batch quantities (simulating consumption)...")
    batch = data_access.get_batch(batch_ids[0])
    item = data_access.get_item(batch['item_id'])
    old_qty = batch['quantity']
    new_qty = old_qty - 0.5
    data_access.update_batch_quantity(batch_ids[0], new_qty)
    print(f"  ✓ Updated {item['name']}: {old_qty} → {new_qty} {item['unit']}")
    
    # Step 7: Summary
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print(f"Database: {db_path}")
    print(f"Total items: {len(all_items)}")
    print(f"Total batches: {len(batch_ids)}")
    print(f"Items expiring soon: {len(expiring)}")
    print("=" * 60)
    
    # Cleanup (optional)
    print("\nNote: Database file 'example_inventory.sqlite' created.")
    print("Run 'rm example_inventory.sqlite' to remove it.")


if __name__ == "__main__":
    main()
