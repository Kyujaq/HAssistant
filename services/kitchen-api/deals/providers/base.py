"""
Abstract base class for deals providers.
"""
from abc import ABC, abstractmethod
from typing import Dict, List


class DealsProvider(ABC):
    """
    Abstract base class for fetching grocery deals and pricing information.
    """

    @abstractmethod
    def get_prices_for(self, items: List[str], postal_code: str) -> Dict:
        """
        Fetch pricing information for a list of items.

        Args:
            items: List of grocery item names to search for
            postal_code: Postal code to use for location-specific deals

        Returns:
            Dictionary containing deals information matching the deals.json schema
        """
        pass
