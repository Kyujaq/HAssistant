"""
Calendar integration tools for overnight intelligence system.

Integrates with Home Assistant calendar for event management.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

# Configuration
HA_BASE_URL = os.getenv("HA_BASE_URL", "http://homeassistant:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")


async def get_calendar_events(
    calendar_entity: str = "calendar.personal",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Get calendar events from Home Assistant.
    
    Args:
        calendar_entity: Calendar entity ID
        start_date: Start date for event query (default: now)
        end_date: End date for event query (default: +7 days)
        
    Returns:
        List of calendar events
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, calendar integration disabled")
        return []
        
    try:
        if start_date is None:
            start_date = datetime.now()
        if end_date is None:
            end_date = start_date + timedelta(days=7)
            
        # Format dates for HA API (ISO format)
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{HA_BASE_URL}/api/calendars/{calendar_entity}",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                },
                params={
                    "start": start_str,
                    "end": end_str
                }
            )
            response.raise_for_status()
            events = response.json()
            logger.info(f"Retrieved {len(events)} calendar events from {calendar_entity}")
            return events
    except Exception as e:
        logger.error(f"Failed to get calendar events: {e}")
        return []


async def create_calendar_event(
    calendar_entity: str,
    summary: str,
    start: datetime,
    end: datetime,
    description: Optional[str] = None,
    location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a calendar event in Home Assistant.
    
    Args:
        calendar_entity: Calendar entity ID
        summary: Event title/summary
        start: Event start datetime
        end: Event end datetime
        description: Optional event description
        location: Optional event location
        
    Returns:
        Created event data
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, calendar integration disabled")
        return {}
        
    try:
        event_data = {
            "summary": summary,
            "start": {
                "dateTime": start.isoformat()
            },
            "end": {
                "dateTime": end.isoformat()
            }
        }
        
        if description:
            event_data["description"] = description
        if location:
            event_data["location"] = location
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{HA_BASE_URL}/api/services/calendar/create_event",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "entity_id": calendar_entity,
                    **event_data
                }
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Created calendar event: {summary}")
            return result
    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        raise


async def get_upcoming_events(days: int = 7) -> List[Dict[str, Any]]:
    """
    Get upcoming events from all calendars.
    
    Args:
        days: Number of days to look ahead
        
    Returns:
        List of upcoming events across all calendars
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, calendar integration disabled")
        return []
        
    try:
        # Get all calendar entities
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{HA_BASE_URL}/api/states",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            states = response.json()
            
        # Filter for calendar entities
        calendars = [
            state["entity_id"]
            for state in states
            if state["entity_id"].startswith("calendar.")
        ]
        
        # Get events from all calendars
        all_events = []
        end_date = datetime.now() + timedelta(days=days)
        
        for calendar in calendars:
            events = await get_calendar_events(calendar, end_date=end_date)
            all_events.extend(events)
            
        # Sort by start time
        all_events.sort(key=lambda x: x.get("start", {}).get("dateTime", ""))
        
        logger.info(f"Retrieved {len(all_events)} upcoming events from {len(calendars)} calendars")
        return all_events
        
    except Exception as e:
        logger.error(f"Failed to get upcoming events: {e}")
        return []
