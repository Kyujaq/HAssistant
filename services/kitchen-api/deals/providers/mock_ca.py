"""
Mock provider for Canadian grocery deals.
Returns hardcoded test data for development and testing purposes.
"""
from datetime import datetime, timedelta
from typing import Dict, List

from .base import DealsProvider


class MockCAProvider(DealsProvider):
    """
    Mock implementation of DealsProvider for Canadian grocery stores.
    Returns hardcoded deals data for testing without requiring a real API.
    """

    def get_prices_for(self, items: List[str], postal_code: str) -> Dict:
        """
        Return mock deals data matching the deals.json schema.

        Args:
            items: List of grocery item names (ignored in mock)
            postal_code: Postal code (ignored in mock)

        Returns:
            Dictionary with hardcoded deals data
        """
        # Generate a valid_to date 7 days from now
        valid_to = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        # Return hardcoded deals matching the expected schema
        return {
            "deals": [
                {
                    "item": "sirloin steak",
                    "best_store": "Metro",
                    "unit_price": 12.99,
                    "unit": "lb",
                    "valid_to": valid_to
                },
                {
                    "item": "chicken breast",
                    "best_store": "Loblaws",
                    "unit_price": 8.99,
                    "unit": "lb",
                    "valid_to": valid_to
                },
                {
                    "item": "salmon fillet",
                    "best_store": "Sobeys",
                    "unit_price": 15.99,
                    "unit": "lb",
                    "valid_to": valid_to
                },
                {
                    "item": "ground beef",
                    "best_store": "Metro",
                    "unit_price": 5.99,
                    "unit": "lb",
                    "valid_to": valid_to
                },
                {
                    "item": "pork chops",
                    "best_store": "Loblaws",
                    "unit_price": 6.99,
                    "unit": "lb",
                    "valid_to": valid_to
                }
            ]
        }
