"""
Home Assistant API Client

A simple, reusable Python client to interact with the Home Assistant API
for reading states and calling services.
"""

import os
import logging
from typing import Dict, Any, Optional
import requests

# Configure logging
logger = logging.getLogger(__name__)


class HAClient:
    """
    Home Assistant API Client
    
    Simple wrapper for interacting with Home Assistant's REST API.
    Reads configuration from environment variables and provides
    methods for common API operations.
    """
    
    def __init__(self):
        """
        Initialize the Home Assistant client.
        
        Reads configuration from environment variables:
        - HA_BASE_URL: Home Assistant base URL (e.g., http://homeassistant:8123)
        - HA_TOKEN: Long-lived access token for authentication
        
        Raises:
            ValueError: If required environment variables are not set
        """
        self.base_url = os.getenv('HA_BASE_URL')
        self.token = os.getenv('HA_TOKEN')
        
        if not self.base_url:
            raise ValueError("HA_BASE_URL environment variable is not set")
        
        if not self.token:
            raise ValueError("HA_TOKEN environment variable is not set")
        
        # Remove trailing slash from base URL if present
        self.base_url = self.base_url.rstrip('/')
        
        # Set up headers for API requests
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        logger.info(f"HAClient initialized with base URL: {self.base_url}")
    
    def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the state of a Home Assistant entity.
        
        Args:
            entity_id: The entity ID (e.g., 'light.living_room')
        
        Returns:
            Dictionary containing the entity state object, or None if not found
        
        Raises:
            requests.exceptions.RequestException: For network-related errors
            ValueError: For invalid responses or status codes
        """
        url = f"{self.base_url}/api/states/{entity_id}"
        
        logger.info(f"Getting state for entity: {entity_id}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            # Handle 404 as entity not found
            if response.status_code == 404:
                logger.warning(f"Entity not found: {entity_id}")
                return None
            
            # Raise exception for other non-200 status codes
            if response.status_code != 200:
                error_msg = f"Failed to get state for {entity_id}: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except Exception:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            state_data = response.json()
            logger.debug(f"State retrieved for {entity_id}: {state_data.get('state')}")
            return state_data
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout getting state for {entity_id}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error getting state for {entity_id}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting state for {entity_id}: {e}")
            raise
    
    def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call a Home Assistant service.
        
        Args:
            domain: The service domain (e.g., 'light', 'switch')
            service: The service name (e.g., 'turn_on', 'turn_off')
            service_data: Optional dictionary of service data/parameters
        
        Returns:
            Dictionary containing the service call response
        
        Raises:
            requests.exceptions.RequestException: For network-related errors
            ValueError: For invalid responses or status codes
        """
        url = f"{self.base_url}/api/services/{domain}/{service}"
        
        logger.info(f"Calling service: {domain}.{service}")
        if service_data:
            logger.debug(f"Service data: {service_data}")
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=service_data or {},
                timeout=30
            )
            
            # Handle non-200 status codes
            if response.status_code != 200:
                error_msg = f"Failed to call service {domain}.{service}: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except Exception:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            result = response.json()
            logger.info(f"Service call successful: {domain}.{service}")
            logger.debug(f"Service response: {result}")
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling service {domain}.{service}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error calling service {domain}.{service}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error calling service {domain}.{service}: {e}")
            raise
