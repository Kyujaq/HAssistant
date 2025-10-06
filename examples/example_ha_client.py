#!/usr/bin/env python3
"""
Example usage of HAClient

Demonstrates how to use the Home Assistant API client wrapper.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from integrations.ha_client import HAClient


def main():
    """Example usage of HAClient."""
    
    # Set environment variables (or load from .env file)
    # os.environ['HA_BASE_URL'] = 'http://homeassistant:8123'
    # os.environ['HA_TOKEN'] = 'your-long-lived-access-token'
    
    # Check if environment variables are set
    if not os.getenv('HA_BASE_URL') or not os.getenv('HA_TOKEN'):
        print("Please set HA_BASE_URL and HA_TOKEN environment variables")
        print("Example:")
        print("  export HA_BASE_URL='http://homeassistant:8123'")
        print("  export HA_TOKEN='your-long-lived-access-token'")
        return
    
    # Initialize the client
    print("Initializing Home Assistant client...")
    client = HAClient()
    print(f"Connected to: {client.base_url}")
    
    # Example 1: Get state of an entity
    print("\n--- Example 1: Get Entity State ---")
    entity_id = 'sun.sun'  # Sun entity is available in every HA installation
    try:
        state = client.get_state(entity_id)
        if state:
            print(f"Entity: {state['entity_id']}")
            print(f"State: {state['state']}")
            print(f"Attributes: {state.get('attributes', {})}")
        else:
            print(f"Entity {entity_id} not found")
    except Exception as e:
        print(f"Error getting state: {e}")
    
    # Example 2: Call a service (turn on a light)
    print("\n--- Example 2: Call Service ---")
    try:
        # This example turns on a light - adjust entity_id as needed
        result = client.call_service(
            domain='light',
            service='turn_on',
            service_data={
                'entity_id': 'light.living_room',
                'brightness': 200
            }
        )
        print(f"Service call result: {result}")
    except Exception as e:
        print(f"Error calling service: {e}")
        print("(This is expected if the entity doesn't exist)")
    
    # Example 3: Call a service without data
    print("\n--- Example 3: Service without data ---")
    try:
        # Get all lights
        result = client.call_service(
            domain='light',
            service='turn_on'
        )
        print(f"Service call result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n✅ Examples completed!")


if __name__ == '__main__':
    main()
