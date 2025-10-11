"""
Example usage of the deals providers.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deals.providers import MockCAProvider


def main():
    """Demonstrate usage of the MockCAProvider"""
    # Create a provider instance
    provider = MockCAProvider()
    
    # Fetch deals (parameters are ignored in mock, but shown for API compatibility)
    items = ["chicken breast", "sirloin steak", "salmon"]
    postal_code = "M5H 2N2"  # Example Toronto postal code
    
    result = provider.get_prices_for(items, postal_code)
    
    # Display results
    print("Grocery Deals:\n")
    for deal in result["deals"]:
        print(f"  • {deal['item'].title()}")
        print(f"    Store: {deal['best_store']}")
        print(f"    Price: ${deal['unit_price']}/{deal['unit']}")
        print(f"    Valid until: {deal['valid_to']}")
        print()


if __name__ == "__main__":
    main()
