#!/usr/bin/env python3
"""
Database Migration Script
Initializes the SQLite database with the schema from schema.sql
This script is idempotent and can be run multiple times safely.
"""

import sqlite3
import os
import sys
from pathlib import Path
from typing import Optional


def get_schema_path() -> Path:
    """Get the path to the schema.sql file."""
    script_dir = Path(__file__).parent
    return script_dir / "schema.sql"


def migrate(db_path: str = "inventory.sqlite", schema_path: Optional[Path] = None) -> bool:
    """
    Initialize or update the database with the schema.
    
    Args:
        db_path: Path to the SQLite database file
        schema_path: Optional path to schema.sql file. If None, uses default location.
        
    Returns:
        bool: True if migration was successful, False otherwise
    """
    if schema_path is None:
        schema_path = get_schema_path()
    
    # Check if schema file exists
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        return False
    
    try:
        # Read schema
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Connect to database (creates if it doesn't exist)
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Execute schema (idempotent due to CREATE TABLE IF NOT EXISTS)
        print("Executing schema...")
        cursor.executescript(schema_sql)
        
        # Commit changes
        conn.commit()
        
        # Verify tables were created
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """)
        tables = cursor.fetchall()
        
        print("\nDatabase initialized successfully!")
        print(f"Tables created: {', '.join(t[0] for t in tables)}")
        
        # Close connection
        cursor.close()
        conn.close()
        
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point for the migration script."""
    # Get database path from environment or use default
    db_path = os.getenv("DB_PATH", "inventory.sqlite")
    
    # Allow command line override
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Kitchen Stack Database Migration")
    print(f"=" * 50)
    
    success = migrate(db_path)
    
    if success:
        print(f"\n✓ Migration completed successfully!")
        print(f"  Database: {db_path}")
        sys.exit(0)
    else:
        print(f"\n✗ Migration failed!", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
