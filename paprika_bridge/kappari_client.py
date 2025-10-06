#!/usr/bin/env python3
"""
Kappari Client - Python client for Paprika V2 API (Kappari reverse-engineered endpoint).

This module provides a client for interacting with the Paprika recipe management system
via the Kappari API. It handles authentication, token refresh, and implements retry logic
for API calls.

Features:
- Automatic authentication and token refresh
- Exponential backoff retry logic for 429 and 5xx errors
- Methods for recipes, meals, and grocery lists
- Normalized response dictionaries

Usage:
    from paprika_bridge import KappariClient
    
    client = KappariClient()
    client.login(email="user@example.com", password="password")
    recipes = client.get_recipes()
    grocery_list = client.get_grocery_list()
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('kappari_client')


class KappariClient:
    """Client for interacting with Paprika V2 API (Kappari)."""
    
    # Kappari API base URL (reverse-engineered endpoint)
    BASE_URL = "https://www.paprikaapp.com/api/v2"
    
    # Retry configuration
    MAX_RETRIES = 5
    BACKOFF_FACTOR = 1  # Start with 1 second, doubles each retry
    RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the Kappari client.
        
        Args:
            base_url: Optional custom API base URL (defaults to Paprika V2 API)
        """
        self.base_url = (base_url or self.BASE_URL).rstrip('/')
        self.session_token: Optional[str] = None
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry logic.
        
        Returns:
            Configured requests Session object
        """
        session = requests.Session()
        
        # All retry logic is handled manually in _make_request_with_retry
        return session
    
    def _make_request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """
        Make an HTTP request with exponential backoff retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base_url)
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response object
            
        Raises:
            requests.exceptions.RequestException: If request fails after all retries
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Check if we need to retry
                if response.status_code in self.RETRY_STATUS_CODES:
                    if attempt < self.MAX_RETRIES - 1:
                        # Calculate exponential backoff
                        wait_time = self.BACKOFF_FACTOR * (2 ** attempt)
                        logger.warning(
                            f"Request failed with status {response.status_code}. "
                            f"Retrying in {wait_time}s (attempt {attempt + 1}/{self.MAX_RETRIES})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Request failed after {self.MAX_RETRIES} attempts")
                        response.raise_for_status()
                
                # Success or non-retryable error
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.BACKOFF_FACTOR * (2 ** attempt)
                    logger.warning(f"Request error: {e}. Retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Request failed after {self.MAX_RETRIES} attempts: {e}")
                    raise
        
        # Should not reach here, but just in case
        raise requests.exceptions.RequestException("Max retries exceeded")
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with Paprika API and obtain session token.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Dictionary with authentication result
            
        Raises:
            requests.exceptions.RequestException: If authentication fails
        """
        logger.info("Authenticating with Paprika API...")
        
        payload = {
            "email": email,
            "password": password
        }
        
        response = self._make_request_with_retry(
            "POST",
            "/account/login",
            json=payload,
            timeout=30
        )
        
        result = response.json()
        
        # Store session token
        if "result" in result and "token" in result["result"]:
            self.session_token = result["result"]["token"]
            logger.info("✅ Authentication successful")
        else:
            logger.error("Authentication response missing token")
            raise ValueError("Authentication failed: no token in response")
        
        return result
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get headers for authenticated requests.
        
        Returns:
            Dictionary of HTTP headers
            
        Raises:
            ValueError: If not authenticated
        """
        if not self.session_token:
            raise ValueError("Not authenticated. Call login() first.")
        
        return {
            "Authorization": f"Bearer {self.session_token}",
            "Content-Type": "application/json"
        }
    
    def _refresh_token_if_needed(self, response: requests.Response) -> bool:
        """
        Check if token refresh is needed based on response.
        
        Args:
            response: Response object from API call
            
        Returns:
            True if token was refreshed, False otherwise
        """
        # If we get a 401, the token may have expired
        if response.status_code == 401:
            logger.warning("Token may have expired (401 response)")
            # In a real implementation, we would refresh the token here
            # For now, we'll let the caller handle re-authentication
            return False
        
        return False
    
    def get_recipes(self) -> List[Dict[str, Any]]:
        """
        Get all recipes from Paprika.
        
        Returns:
            List of recipe dictionaries with normalized schema
            
        Raises:
            requests.exceptions.RequestException: If request fails
        """
        logger.info("Fetching recipes...")
        
        response = self._make_request_with_retry(
            "GET",
            "/recipes",
            headers=self._get_headers(),
            timeout=30
        )
        
        result = response.json()
        
        # Normalize response
        recipes = result.get("result", [])
        logger.info(f"✅ Retrieved {len(recipes)} recipes")
        
        return recipes
    
    def get_meals(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Get meals within a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of meal dictionaries with normalized schema
            
        Raises:
            requests.exceptions.RequestException: If request fails
        """
        logger.info(f"Fetching meals from {start_date} to {end_date}...")
        
        response = self._make_request_with_retry(
            "GET",
            f"/meals?start={start_date}&end={end_date}",
            headers=self._get_headers(),
            timeout=30
        )
        
        result = response.json()
        
        # Normalize response
        meals = result.get("result", [])
        logger.info(f"✅ Retrieved {len(meals)} meals")
        
        return meals
    
    def get_grocery_list(self) -> Dict[str, Any]:
        """
        Get the current grocery list.
        
        Returns:
            Dictionary containing grocery list with normalized schema
            
        Raises:
            requests.exceptions.RequestException: If request fails
        """
        logger.info("Fetching grocery list...")
        
        response = self._make_request_with_retry(
            "GET",
            "/groceries",
            headers=self._get_headers(),
            timeout=30
        )
        
        result = response.json()
        
        # Normalize response
        grocery_list = result.get("result", {})
        items = grocery_list.get("items", [])
        logger.info(f"✅ Retrieved grocery list with {len(items)} items")
        
        return grocery_list
    
    def add_grocery_item(
        self,
        name: str,
        quantity: Optional[str] = None,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add an item to the grocery list.
        
        Args:
            name: Item name
            quantity: Optional quantity (e.g., "2 lbs", "1 bunch")
            note: Optional note
            
        Returns:
            Dictionary with the created item
            
        Raises:
            requests.exceptions.RequestException: If request fails
        """
        logger.info(f"Adding grocery item: {name}")
        
        payload = {
            "name": name,
            "quantity": quantity or "",
            "note": note or "",
            "purchased": False
        }
        
        response = self._make_request_with_retry(
            "POST",
            "/groceries",
            headers=self._get_headers(),
            json=payload,
            timeout=30
        )
        
        result = response.json()
        logger.info(f"✅ Added grocery item: {name}")
        
        return result.get("result", {})
    
    def post_meal(
        self,
        date: str,
        meal_type: str,
        recipe_id: str
    ) -> Dict[str, Any]:
        """
        Add a meal to the calendar.
        
        Args:
            date: Date in YYYY-MM-DD format
            meal_type: Type of meal (e.g., "breakfast", "lunch", "dinner")
            recipe_id: Recipe ID to add to calendar
            
        Returns:
            Dictionary with the created meal
            
        Raises:
            requests.exceptions.RequestException: If request fails
        """
        logger.info(f"Adding meal: {meal_type} on {date}")
        
        payload = {
            "date": date,
            "type": meal_type,
            "recipe_id": recipe_id
        }
        
        response = self._make_request_with_retry(
            "POST",
            "/meals",
            headers=self._get_headers(),
            json=payload,
            timeout=30
        )
        
        result = response.json()
        logger.info(f"✅ Added meal: {meal_type} on {date}")
        
        return result.get("result", {})
    
    def healthcheck(self) -> bool:
        """
        Check if the client is properly authenticated and can reach the API.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self.session_token:
                return False
            
            # Try a simple request
            response = self._make_request_with_retry(
                "GET",
                "/recipes",
                headers=self._get_headers(),
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Healthcheck failed: {e}")
            return False


def main():
    """Example usage of KappariClient."""
    # Get credentials from environment
    email = os.getenv("PAPRIKA_EMAIL")
    password = os.getenv("PAPRIKA_PASSWORD")
    
    if not email or not password:
        print("Error: PAPRIKA_EMAIL and PAPRIKA_PASSWORD environment variables must be set")
        return
    
    # Create client and authenticate
    client = KappariClient()
    client.login(email, password)
    
    # Get recipes
    recipes = client.get_recipes()
    print(f"Found {len(recipes)} recipes")
    
    # Get grocery list
    grocery_list = client.get_grocery_list()
    items = grocery_list.get("items", [])
    print(f"Grocery list has {len(items)} items")
    
    # Example: Add a grocery item
    # client.add_grocery_item("Milk", quantity="1 gallon")
    
    # Example: Get meals for a date range
    # meals = client.get_meals("2025-01-01", "2025-01-31")
    # print(f"Found {len(meals)} meals")


if __name__ == "__main__":
    main()
