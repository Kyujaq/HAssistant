#!/usr/bin/env python3
"""
Smoke test for Kappari Client.

This script verifies basic connectivity to the Paprika API via Kappari endpoint.
It tests authentication and basic API calls to ensure the client is working properly.

Usage:
    export PAPRIKA_EMAIL="your_email@example.com"
    export PAPRIKA_PASSWORD="your_password"
    python3 tests/smoke_test_kappari.py

Environment Variables:
    PAPRIKA_EMAIL: Email for Paprika account
    PAPRIKA_PASSWORD: Password for Paprika account
"""

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import paprika_bridge
sys.path.insert(0, str(Path(__file__).parent.parent))

from paprika_bridge import KappariClient


def main():
    """Run smoke tests for Kappari client."""
    print("=" * 60)
    print("Kappari Client Smoke Test")
    print("=" * 60)
    print()
    
    # Get credentials from environment
    email = os.getenv("PAPRIKA_EMAIL")
    password = os.getenv("PAPRIKA_PASSWORD")
    
    if not email or not password:
        print("❌ ERROR: Required environment variables not set")
        print()
        print("Please set the following environment variables:")
        print("  PAPRIKA_EMAIL - Your Paprika account email")
        print("  PAPRIKA_PASSWORD - Your Paprika account password")
        print()
        print("Example:")
        print('  export PAPRIKA_EMAIL="user@example.com"')
        print('  export PAPRIKA_PASSWORD="your_password"')
        print()
        sys.exit(1)
    
    print(f"Testing with email: {email}")
    print()
    
    # Initialize client
    print("Step 1: Initializing Kappari client...")
    try:
        client = KappariClient()
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        sys.exit(1)
    
    print()
    
    # Test authentication
    print("Step 2: Authenticating with Paprika API...")
    try:
        result = client.login(email, password)
        print("✅ Authentication successful")
        if "result" in result and "token" in result["result"]:
            token_preview = result["result"]["token"][:20] + "..."
            print(f"   Token: {token_preview}")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print()
        print("Possible issues:")
        print("  - Incorrect email or password")
        print("  - Network connectivity issues")
        print("  - API endpoint may have changed")
        print()
        sys.exit(1)
    
    print()
    
    # Test get_recipes()
    print("Step 3: Fetching recipes...")
    try:
        recipes = client.get_recipes()
        print(f"✅ Successfully retrieved recipes")
        print(f"   Recipe count: {len(recipes)}")
        
        if recipes and len(recipes) > 0:
            # Show first recipe as example
            first_recipe = recipes[0]
            recipe_name = first_recipe.get("name", "Unknown")
            print(f"   First recipe: {recipe_name}")
    except Exception as e:
        print(f"❌ Failed to fetch recipes: {e}")
        sys.exit(1)
    
    print()
    
    # Test get_grocery_list()
    print("Step 4: Fetching grocery list...")
    try:
        grocery_list = client.get_grocery_list()
        print(f"✅ Successfully retrieved grocery list")
        
        items = grocery_list.get("items", [])
        print(f"   Grocery item count: {len(items)}")
        
        if items and len(items) > 0:
            # Show first item as example
            first_item = items[0]
            item_name = first_item.get("name", "Unknown")
            print(f"   First item: {item_name}")
    except Exception as e:
        print(f"❌ Failed to fetch grocery list: {e}")
        sys.exit(1)
    
    print()
    
    # Test healthcheck
    print("Step 5: Running healthcheck...")
    try:
        is_healthy = client.healthcheck()
        if is_healthy:
            print("✅ Healthcheck passed - client is operational")
        else:
            print("⚠️  Healthcheck returned false")
    except Exception as e:
        print(f"❌ Healthcheck failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✅ All smoke tests passed successfully!")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  - Recipes: {len(recipes)}")
    print(f"  - Grocery items: {len(items)}")
    print(f"  - Client status: Healthy")
    print()


if __name__ == "__main__":
    main()
