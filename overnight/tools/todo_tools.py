"""
To-Do list tools for Home Assistant integration.

Interfaces with Home Assistant To-Do lists for task management.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

# Configuration
HA_BASE_URL = os.getenv("HA_BASE_URL", "http://homeassistant:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")


async def get_todo_items(
    entity_id: str = "todo.tasks",
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get to-do items from a Home Assistant To-Do list.
    
    Args:
        entity_id: To-Do list entity ID (e.g., "todo.tasks")
        status: Filter by status ("needs_action", "completed", or None for all)
        
    Returns:
        List of to-do items
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, using mock data")
        return _get_mock_todo_items()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get to-do list items using the to-do integration API
            response = await client.get(
                f"{HA_BASE_URL}/api/services/todo/get_items",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "entity_id": entity_id,
                    "status": status or ["needs_action", "completed"]
                }
            )
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            
            # Filter by status if specified
            if status:
                items = [item for item in items if item.get("status") == status]
            
            logger.info(f"Retrieved {len(items)} to-do items from {entity_id}")
            return items
            
    except Exception as e:
        logger.error(f"Failed to get to-do items from {entity_id}: {e}")
        # Try alternative method: get state attributes
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{HA_BASE_URL}/api/states/{entity_id}",
                    headers={
                        "Authorization": f"Bearer {HA_TOKEN}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                state = response.json()
                
                # Extract items from attributes
                items = state.get("attributes", {}).get("items", [])
                
                if status:
                    items = [item for item in items if item.get("status") == status]
                
                logger.info(f"Retrieved {len(items)} to-do items from state attributes")
                return items
        except Exception as e2:
            logger.error(f"Alternative method also failed: {e2}")
            return _get_mock_todo_items()


async def get_upcoming_tasks(
    entity_id: str = "todo.tasks",
    days_ahead: int = 1
) -> List[Dict[str, Any]]:
    """
    Get tasks that are due in the next N days.
    
    Args:
        entity_id: To-Do list entity ID
        days_ahead: Number of days to look ahead (default: 1 for tomorrow)
        
    Returns:
        List of upcoming tasks
    """
    try:
        all_items = await get_todo_items(entity_id, status="needs_action")
        
        # Filter for items with due dates in the next N days
        now = datetime.now()
        upcoming = []
        
        for item in all_items:
            due_date_str = item.get("due")
            if not due_date_str:
                # Items without due dates are considered "upcoming"
                upcoming.append(item)
                continue
            
            try:
                due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
                days_until_due = (due_date - now).days
                
                if 0 <= days_until_due <= days_ahead:
                    upcoming.append(item)
            except (ValueError, AttributeError):
                # If we can't parse the date, include it
                upcoming.append(item)
        
        logger.info(f"Found {len(upcoming)} tasks due in the next {days_ahead} day(s)")
        return upcoming
        
    except Exception as e:
        logger.error(f"Failed to get upcoming tasks: {e}")
        return []


async def create_todo_item(
    entity_id: str,
    summary: str,
    description: Optional[str] = None,
    due_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Create a new to-do item.
    
    Args:
        entity_id: To-Do list entity ID
        summary: Item summary/title
        description: Optional item description
        due_date: Optional due date
        
    Returns:
        Created item data
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, cannot create to-do item")
        return {}
    
    try:
        item_data = {
            "summary": summary,
            "status": "needs_action"
        }
        
        if description:
            item_data["description"] = description
        
        if due_date:
            item_data["due"] = due_date.isoformat()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{HA_BASE_URL}/api/services/todo/add_item",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "entity_id": entity_id,
                    "item": summary,
                    **item_data
                }
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Created to-do item: {summary}")
            return result
            
    except Exception as e:
        logger.error(f"Failed to create to-do item: {e}")
        raise


async def update_todo_item(
    entity_id: str,
    item_uid: str,
    status: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing to-do item.
    
    Args:
        entity_id: To-Do list entity ID
        item_uid: Unique identifier of the item
        status: New status ("needs_action" or "completed")
        summary: New summary
        description: New description
        
    Returns:
        Update result
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, cannot update to-do item")
        return {}
    
    try:
        update_data = {"uid": item_uid}
        
        if status:
            update_data["status"] = status
        if summary:
            update_data["summary"] = summary
        if description:
            update_data["description"] = description
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{HA_BASE_URL}/api/services/todo/update_item",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "entity_id": entity_id,
                    **update_data
                }
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Updated to-do item: {item_uid}")
            return result
            
    except Exception as e:
        logger.error(f"Failed to update to-do item: {e}")
        raise


def _get_mock_todo_items() -> List[Dict[str, Any]]:
    """Generate mock to-do items for testing"""
    tomorrow = (datetime.now() + timedelta(days=1)).isoformat()
    
    return [
        {
            "uid": "task-1",
            "summary": "Review home automation scripts",
            "description": "Check and update automation scripts for efficiency",
            "status": "needs_action",
            "due": tomorrow
        },
        {
            "uid": "task-2",
            "summary": "Research smart thermostat integration",
            "description": "Look into integrating new thermostat with Home Assistant",
            "status": "needs_action",
            "due": tomorrow
        },
        {
            "uid": "task-3",
            "summary": "Update security camera firmware",
            "description": "Check for firmware updates on all cameras",
            "status": "needs_action",
            "due": None
        },
        {
            "uid": "task-4",
            "summary": "Plan smart lighting zones",
            "description": "Design lighting zones for better control",
            "status": "needs_action",
            "due": None
        }
    ]


from datetime import timedelta
