"""
Unit tests for the data access layer
Uses pytest and in-memory SQLite database for testing
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import data_access
from db.migrate import migrate


@pytest.fixture
def test_db():
    """
    Create a temporary test database file with schema applied.
    Yields the database path and cleans up after test.
    """
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.sqlite')
    os.close(fd)
    
    # Set environment variable for data_access module
    os.environ["DB_PATH"] = db_path
    
    # Get schema path
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    
    # Apply schema using migrate function
    success = migrate(db_path, schema_path)
    assert success, "Failed to apply schema to test database"
    
    yield db_path
    
    # Cleanup
    if "DB_PATH" in os.environ:
        del os.environ["DB_PATH"]
    
    # Remove temporary database file
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def sample_item_data():
    """Provide sample item data for tests."""
    return {
        'name': 'Milk',
        'category': 'dairy',
        'unit': 'L',
        'calories_per_unit': 600.0,
        'protein_per_unit': 32.0,
        'carbs_per_unit': 48.0,
        'fat_per_unit': 32.0
    }


@pytest.fixture
def sample_batch_data():
    """Provide sample batch data for tests."""
    today = datetime.now().strftime('%Y-%m-%d')
    future = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    return {
        'item_id': 1,  # Will be replaced with actual item_id in tests
        'quantity': 2.0,
        'purchase_date': today,
        'expiration_date': future,
        'location': 'fridge',
        'cost': 5.99,
        'notes': 'Organic milk'
    }


class TestDatabaseConnection:
    """Test database connection functionality."""
    
    def test_get_db_connection(self, test_db):
        """Test that we can get a database connection."""
        conn = data_access.get_db_connection(test_db)
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        conn.close()
    
    def test_foreign_keys_enabled(self, test_db):
        """Test that foreign keys are enabled."""
        conn = data_access.get_db_connection(test_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        result = cursor.fetchone()
        conn.close()
        assert result[0] == 1, "Foreign keys should be enabled"


class TestItemOperations:
    """Test item CRUD operations."""
    
    def test_add_item(self, test_db, sample_item_data):
        """Test adding a new item."""
        item_id = data_access.add_item(sample_item_data)
        assert item_id > 0
    
    def test_add_item_missing_required_field(self, test_db):
        """Test that adding an item without required fields raises ValueError."""
        incomplete_data = {'name': 'Bread'}
        with pytest.raises(ValueError, match="Missing required field"):
            data_access.add_item(incomplete_data)
    
    def test_add_duplicate_item(self, test_db, sample_item_data):
        """Test that adding a duplicate item raises an error."""
        data_access.add_item(sample_item_data)
        with pytest.raises(sqlite3.Error, match="already exists"):
            data_access.add_item(sample_item_data)
    
    def test_get_item(self, test_db, sample_item_data):
        """Test retrieving an item by ID."""
        item_id = data_access.add_item(sample_item_data)
        item = data_access.get_item(item_id)
        
        assert item is not None
        assert item['item_id'] == item_id
        assert item['name'] == sample_item_data['name']
        assert item['category'] == sample_item_data['category']
        assert item['unit'] == sample_item_data['unit']
        assert item['calories_per_unit'] == sample_item_data['calories_per_unit']
    
    def test_get_nonexistent_item(self, test_db):
        """Test that getting a non-existent item returns None."""
        item = data_access.get_item(9999)
        assert item is None
    
    def test_get_all_items(self, test_db, sample_item_data):
        """Test retrieving all items."""
        # Add multiple items
        data_access.add_item(sample_item_data)
        
        sample_item_data2 = sample_item_data.copy()
        sample_item_data2['name'] = 'Bread'
        sample_item_data2['category'] = 'bakery'
        data_access.add_item(sample_item_data2)
        
        all_items = data_access.get_all_items()
        assert len(all_items) == 2
        assert all_items[0]['name'] in ['Milk', 'Bread']


class TestBatchOperations:
    """Test batch CRUD operations."""
    
    def test_add_batch(self, test_db, sample_item_data, sample_batch_data):
        """Test adding a new batch."""
        # First add an item
        item_id = data_access.add_item(sample_item_data)
        sample_batch_data['item_id'] = item_id
        
        batch_id = data_access.add_batch(sample_batch_data)
        assert batch_id > 0
    
    def test_add_batch_missing_required_field(self, test_db, sample_item_data):
        """Test that adding a batch without required fields raises ValueError."""
        item_id = data_access.add_item(sample_item_data)
        incomplete_data = {'item_id': item_id}
        with pytest.raises(ValueError, match="Missing required field"):
            data_access.add_batch(incomplete_data)
    
    def test_add_batch_invalid_item_id(self, test_db, sample_batch_data):
        """Test that adding a batch with invalid item_id raises an error."""
        sample_batch_data['item_id'] = 9999
        with pytest.raises(sqlite3.Error):
            data_access.add_batch(sample_batch_data)
    
    def test_get_batch(self, test_db, sample_item_data, sample_batch_data):
        """Test retrieving a batch by ID."""
        item_id = data_access.add_item(sample_item_data)
        sample_batch_data['item_id'] = item_id
        
        batch_id = data_access.add_batch(sample_batch_data)
        batch = data_access.get_batch(batch_id)
        
        assert batch is not None
        assert batch['batch_id'] == batch_id
        assert batch['item_id'] == item_id
        assert batch['quantity'] == sample_batch_data['quantity']
        assert batch['location'] == sample_batch_data['location']
    
    def test_get_nonexistent_batch(self, test_db):
        """Test that getting a non-existent batch returns None."""
        batch = data_access.get_batch(9999)
        assert batch is None
    
    def test_update_batch_quantity(self, test_db, sample_item_data, sample_batch_data):
        """Test updating batch quantity."""
        item_id = data_access.add_item(sample_item_data)
        sample_batch_data['item_id'] = item_id
        
        batch_id = data_access.add_batch(sample_batch_data)
        
        # Update quantity
        new_qty = 1.5
        success = data_access.update_batch_quantity(batch_id, new_qty)
        assert success is True
        
        # Verify update
        batch = data_access.get_batch(batch_id)
        assert batch['quantity'] == new_qty
    
    def test_update_nonexistent_batch_quantity(self, test_db):
        """Test that updating a non-existent batch returns False."""
        success = data_access.update_batch_quantity(9999, 1.0)
        assert success is False


class TestExpiringItems:
    """Test expiring items functionality."""
    
    def test_get_expiring_items(self, test_db, sample_item_data):
        """Test retrieving expiring items."""
        # Add an item
        item_id = data_access.add_item(sample_item_data)
        
        # Add batch expiring in 3 days
        today = datetime.now().strftime('%Y-%m-%d')
        expiring_soon = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        batch_data = {
            'item_id': item_id,
            'quantity': 1.0,
            'purchase_date': today,
            'expiration_date': expiring_soon,
            'location': 'fridge'
        }
        data_access.add_batch(batch_data)
        
        # Add batch expiring in 30 days
        expiring_later = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        batch_data2 = {
            'item_id': item_id,
            'quantity': 2.0,
            'purchase_date': today,
            'expiration_date': expiring_later,
            'location': 'pantry'
        }
        data_access.add_batch(batch_data2)
        
        # Get items expiring in next 7 days
        expiring = data_access.get_expiring_items(7)
        assert len(expiring) == 1
        assert expiring[0]['item_name'] == sample_item_data['name']
        assert expiring[0]['quantity'] == 1.0
    
    def test_get_expiring_items_excludes_past(self, test_db, sample_item_data):
        """Test that expired items are excluded."""
        item_id = data_access.add_item(sample_item_data)
        
        # Add batch that already expired
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        batch_data = {
            'item_id': item_id,
            'quantity': 1.0,
            'purchase_date': today,
            'expiration_date': yesterday,
            'location': 'fridge'
        }
        data_access.add_batch(batch_data)
        
        # Should not return expired items
        expiring = data_access.get_expiring_items(7)
        assert len(expiring) == 0
    
    def test_get_expiring_items_excludes_zero_quantity(self, test_db, sample_item_data):
        """Test that batches with zero quantity are excluded."""
        item_id = data_access.add_item(sample_item_data)
        
        # Add batch with zero quantity
        today = datetime.now().strftime('%Y-%m-%d')
        expiring_soon = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        batch_data = {
            'item_id': item_id,
            'quantity': 0.0,
            'purchase_date': today,
            'expiration_date': expiring_soon,
            'location': 'fridge'
        }
        data_access.add_batch(batch_data)
        
        # Should not return zero quantity items
        expiring = data_access.get_expiring_items(7)
        assert len(expiring) == 0
    
    def test_get_expiring_items_custom_days(self, test_db, sample_item_data):
        """Test getting expiring items with custom day range."""
        item_id = data_access.add_item(sample_item_data)
        
        # Add batch expiring in 10 days
        today = datetime.now().strftime('%Y-%m-%d')
        expiring_later = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
        batch_data = {
            'item_id': item_id,
            'quantity': 1.0,
            'purchase_date': today,
            'expiration_date': expiring_later,
            'location': 'fridge'
        }
        data_access.add_batch(batch_data)
        
        # Should not be in 7-day window
        expiring_7 = data_access.get_expiring_items(7)
        assert len(expiring_7) == 0
        
        # Should be in 14-day window
        expiring_14 = data_access.get_expiring_items(14)
        assert len(expiring_14) == 1
