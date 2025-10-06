"""
Data Access Layer for Kitchen Stack Database
Provides functions for interacting with the SQLite inventory database.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
import os


# Database connection settings
DEFAULT_DB_PATH = "inventory.sqlite"


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Create and return a database connection.
    
    Args:
        db_path: Optional path to the database file. If None, uses default.
        
    Returns:
        sqlite3.Connection: Database connection object
        
    Raises:
        sqlite3.Error: If connection fails
    """
    if db_path is None:
        db_path = os.getenv("DB_PATH", DEFAULT_DB_PATH)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to connect to database: {e}")


def add_item(item_data: Dict[str, Any]) -> int:
    """
    Add a new item to the items table.
    
    Args:
        item_data: Dictionary containing item fields:
            - name (str, required): Item name
            - category (str, required): Item category
            - unit (str, required): Unit of measurement
            - calories_per_unit (float, optional): Calories per unit
            - protein_per_unit (float, optional): Protein per unit
            - carbs_per_unit (float, optional): Carbs per unit
            - fat_per_unit (float, optional): Fat per unit
            
    Returns:
        int: ID of the newly created item
        
    Raises:
        ValueError: If required fields are missing
        sqlite3.Error: If database operation fails
    """
    # Validate required fields
    required_fields = ['name', 'category', 'unit']
    for field in required_fields:
        if field not in item_data:
            raise ValueError(f"Missing required field: {field}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO items (
                name, category, unit, calories_per_unit, 
                protein_per_unit, carbs_per_unit, fat_per_unit
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item_data['name'],
            item_data['category'],
            item_data['unit'],
            item_data.get('calories_per_unit'),
            item_data.get('protein_per_unit'),
            item_data.get('carbs_per_unit'),
            item_data.get('fat_per_unit')
        ))
        
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return item_id
        
    except sqlite3.IntegrityError as e:
        raise sqlite3.Error(f"Item already exists or constraint violation: {e}")
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to add item: {e}")


def get_item(item_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve an item by its ID.
    
    Args:
        item_id: ID of the item to retrieve
        
    Returns:
        Optional[Dict[str, Any]]: Dictionary containing item data, or None if not found
        
    Raises:
        sqlite3.Error: If database operation fails
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM items WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        return dict(row)
        
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to get item: {e}")


def add_batch(batch_data: Dict[str, Any]) -> int:
    """
    Add a new batch to the batches table.
    
    Args:
        batch_data: Dictionary containing batch fields:
            - item_id (int, required): ID of the item
            - quantity (float, required): Quantity of the batch
            - purchase_date (str, required): Purchase date (YYYY-MM-DD)
            - expiration_date (str, optional): Expiration date (YYYY-MM-DD)
            - location (str, optional): Storage location
            - cost (float, optional): Purchase cost
            - notes (str, optional): Additional notes
            
    Returns:
        int: ID of the newly created batch
        
    Raises:
        ValueError: If required fields are missing
        sqlite3.Error: If database operation fails
    """
    # Validate required fields
    required_fields = ['item_id', 'quantity', 'purchase_date']
    for field in required_fields:
        if field not in batch_data:
            raise ValueError(f"Missing required field: {field}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO batches (
                item_id, quantity, purchase_date, expiration_date,
                location, cost, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_data['item_id'],
            batch_data['quantity'],
            batch_data['purchase_date'],
            batch_data.get('expiration_date'),
            batch_data.get('location'),
            batch_data.get('cost'),
            batch_data.get('notes')
        ))
        
        batch_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return batch_id
        
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to add batch: {e}")


def get_batch(batch_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a batch by its ID.
    
    Args:
        batch_id: ID of the batch to retrieve
        
    Returns:
        Optional[Dict[str, Any]]: Dictionary containing batch data, or None if not found
        
    Raises:
        sqlite3.Error: If database operation fails
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        return dict(row)
        
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to get batch: {e}")


def update_batch_quantity(batch_id: int, new_qty: float) -> bool:
    """
    Update the quantity of a batch.
    
    Args:
        batch_id: ID of the batch to update
        new_qty: New quantity value
        
    Returns:
        bool: True if update was successful, False if batch not found
        
    Raises:
        sqlite3.Error: If database operation fails
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE batches 
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = ?
        """, (new_qty, batch_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return rows_affected > 0
        
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to update batch quantity: {e}")


def get_all_items() -> List[Dict[str, Any]]:
    """
    Retrieve all items from the database.
    
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing item data
        
    Raises:
        sqlite3.Error: If database operation fails
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM items ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to get all items: {e}")


def get_expiring_items(days_in_future: int = 7) -> List[Dict[str, Any]]:
    """
    Retrieve batches that are expiring within the specified number of days.
    
    Args:
        days_in_future: Number of days to look ahead for expiring items
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing batch and item data
        
    Raises:
        sqlite3.Error: If database operation fails
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Calculate the target date
        target_date = (datetime.now() + timedelta(days=days_in_future)).strftime('%Y-%m-%d')
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT 
                b.*,
                i.name as item_name,
                i.category as item_category,
                i.unit as item_unit
            FROM batches b
            JOIN items i ON b.item_id = i.item_id
            WHERE b.expiration_date IS NOT NULL
                AND b.expiration_date <= ?
                AND b.expiration_date >= ?
                AND b.quantity > 0
            ORDER BY b.expiration_date ASC
        """, (target_date, current_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to get expiring items: {e}")
