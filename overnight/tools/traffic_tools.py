"""
Traffic analysis tools for commute planning.

Integrates with traffic APIs to predict travel times.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

# Configuration
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
TRAFFIC_API_TIMEOUT = 10.0


async def get_predicted_travel_time(
    origin: str,
    destination: str,
    departure_time: Optional[datetime] = None,
    traffic_model: str = "best_guess"
) -> Dict[str, Any]:
    """
    Get predicted travel time using Google Maps API or fallback.
    
    Args:
        origin: Origin address or coordinates
        destination: Destination address or coordinates
        departure_time: When to depart (default: now)
        traffic_model: Traffic prediction model (best_guess, pessimistic, optimistic)
        
    Returns:
        Dict with travel time predictions
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.warning("GOOGLE_MAPS_API_KEY not set, using mock data")
        return _get_mock_travel_time(origin, destination, departure_time)
    
    try:
        if departure_time is None:
            departure_time = datetime.now()
        
        # Convert datetime to unix timestamp
        departure_timestamp = int(departure_time.timestamp())
        
        async with httpx.AsyncClient(timeout=TRAFFIC_API_TIMEOUT) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params={
                    "origin": origin,
                    "destination": destination,
                    "departure_time": departure_timestamp,
                    "traffic_model": traffic_model,
                    "key": GOOGLE_MAPS_API_KEY
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("routes"):
                logger.warning(f"Google Maps API returned status: {data.get('status')}")
                return _get_mock_travel_time(origin, destination, departure_time)
            
            route = data["routes"][0]
            leg = route["legs"][0]
            
            # Extract travel time with traffic
            duration_in_traffic = leg.get("duration_in_traffic", leg.get("duration", {}))
            baseline_duration = leg.get("duration", {})
            
            result = {
                "origin": leg["start_address"],
                "destination": leg["end_address"],
                "predicted_duration_seconds": duration_in_traffic.get("value", 0),
                "predicted_duration_minutes": duration_in_traffic.get("value", 0) // 60,
                "baseline_duration_seconds": baseline_duration.get("value", 0),
                "baseline_duration_minutes": baseline_duration.get("value", 0) // 60,
                "distance_meters": leg["distance"]["value"],
                "distance_text": leg["distance"]["text"],
                "departure_time": departure_time.isoformat(),
                "source": "google_maps"
            }
            
            logger.info(f"Travel time from '{origin}' to '{destination}': {result['predicted_duration_minutes']} min")
            return result
            
    except Exception as e:
        logger.error(f"Failed to get travel time from Google Maps: {e}")
        return _get_mock_travel_time(origin, destination, departure_time)


def _get_mock_travel_time(
    origin: str,
    destination: str,
    departure_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Generate mock travel time data for testing/fallback.
    
    Args:
        origin: Origin location
        destination: Destination location
        departure_time: Departure time
        
    Returns:
        Mock travel time data
    """
    if departure_time is None:
        departure_time = datetime.now()
    
    # Simple heuristic: estimate based on time of day
    hour = departure_time.hour
    
    # Baseline: 30 minutes
    baseline_minutes = 30
    
    # Add traffic delays during rush hours
    if 7 <= hour <= 9 or 17 <= hour <= 19:
        # Rush hour: 50% longer
        predicted_minutes = int(baseline_minutes * 1.5)
        traffic_condition = "heavy"
    elif 6 <= hour <= 22:
        # Daytime: 20% longer
        predicted_minutes = int(baseline_minutes * 1.2)
        traffic_condition = "moderate"
    else:
        # Night: minimal traffic
        predicted_minutes = baseline_minutes
        traffic_condition = "light"
    
    result = {
        "origin": origin,
        "destination": destination,
        "predicted_duration_seconds": predicted_minutes * 60,
        "predicted_duration_minutes": predicted_minutes,
        "baseline_duration_seconds": baseline_minutes * 60,
        "baseline_duration_minutes": baseline_minutes,
        "distance_meters": 15000,  # Mock: ~15km
        "distance_text": "15 km",
        "departure_time": departure_time.isoformat(),
        "traffic_condition": traffic_condition,
        "source": "mock"
    }
    
    logger.info(f"Mock travel time from '{origin}' to '{destination}': {predicted_minutes} min ({traffic_condition} traffic)")
    return result


async def analyze_commute_impact(
    predicted_minutes: int,
    baseline_minutes: int,
    threshold_percent: float = 20.0
) -> Dict[str, Any]:
    """
    Analyze if traffic impact warrants an alert.
    
    Args:
        predicted_minutes: Predicted travel time with traffic
        baseline_minutes: Baseline travel time without traffic
        threshold_percent: Alert threshold (e.g., 20% means alert if 20% longer)
        
    Returns:
        Analysis result with alert recommendation
    """
    if baseline_minutes == 0:
        baseline_minutes = 1  # Avoid division by zero
    
    delay_minutes = predicted_minutes - baseline_minutes
    delay_percent = (delay_minutes / baseline_minutes) * 100
    
    should_alert = delay_percent >= threshold_percent
    
    if delay_percent >= 50:
        severity = "high"
        reasoning = f"Heavy traffic expected. Travel time {delay_percent:.0f}% longer than normal (+{delay_minutes} min)."
    elif delay_percent >= threshold_percent:
        severity = "medium"
        reasoning = f"Moderate traffic expected. Travel time {delay_percent:.0f}% longer than normal (+{delay_minutes} min)."
    else:
        severity = "low"
        reasoning = f"Normal traffic conditions. Expected travel time: {predicted_minutes} min."
    
    return {
        "should_alert": should_alert,
        "severity": severity,
        "delay_minutes": delay_minutes,
        "delay_percent": delay_percent,
        "reasoning": reasoning,
        "predicted_minutes": predicted_minutes,
        "baseline_minutes": baseline_minutes
    }
