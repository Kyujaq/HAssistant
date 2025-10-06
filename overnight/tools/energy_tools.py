"""
Energy dashboard tools for Home Assistant integration.

Interfaces with Home Assistant Energy Dashboard for consumption analysis.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

# Configuration
HA_BASE_URL = os.getenv("HA_BASE_URL", "http://homeassistant:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")


async def get_energy_consumption_24h() -> Dict[str, Any]:
    """
    Get total energy consumption for the last 24 hours.
    
    Returns:
        Dict with total consumption and period info
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, using mock data")
        return _get_mock_energy_data()
    
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get energy sensor statistics
            response = await client.post(
                f"{HA_BASE_URL}/api/history/period/{start_time.isoformat()}",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                },
                params={
                    "filter_entity_id": "sensor.energy_consumption",
                    "end_time": end_time.isoformat()
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if not data:
                logger.warning("No energy data returned from Home Assistant")
                return _get_mock_energy_data()
            
            # Calculate total consumption from sensor data
            total_kwh = _calculate_total_consumption(data)
            
            result = {
                "total_kwh": total_kwh,
                "period_start": start_time.isoformat(),
                "period_end": end_time.isoformat(),
                "period_hours": 24,
                "source": "home_assistant"
            }
            
            logger.info(f"Retrieved 24h energy consumption: {total_kwh:.2f} kWh")
            return result
            
    except Exception as e:
        logger.error(f"Failed to get energy consumption: {e}")
        return _get_mock_energy_data()


async def get_device_energy_breakdown() -> List[Dict[str, Any]]:
    """
    Get energy consumption breakdown by device for the last 24 hours.
    
    Returns:
        List of devices with their consumption
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, using mock data")
        return _get_mock_device_breakdown()
    
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get all energy sensors
            response = await client.get(
                f"{HA_BASE_URL}/api/states",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            states = response.json()
            
            # Filter for individual device energy sensors
            energy_sensors = [
                state for state in states
                if state["entity_id"].startswith("sensor.") and
                   "energy" in state["entity_id"] and
                   state.get("attributes", {}).get("unit_of_measurement") in ["kWh", "Wh"]
            ]
            
            if not energy_sensors:
                logger.warning("No device energy sensors found")
                return _get_mock_device_breakdown()
            
            # Get consumption for each device
            devices = []
            for sensor in energy_sensors[:20]:  # Limit to top 20 devices
                entity_id = sensor["entity_id"]
                device_name = sensor.get("attributes", {}).get("friendly_name", entity_id)
                
                # Get historical data for this device
                hist_response = await client.post(
                    f"{HA_BASE_URL}/api/history/period/{start_time.isoformat()}",
                    headers={
                        "Authorization": f"Bearer {HA_TOKEN}",
                        "Content-Type": "application/json"
                    },
                    params={
                        "filter_entity_id": entity_id,
                        "end_time": end_time.isoformat()
                    }
                )
                hist_response.raise_for_status()
                hist_data = hist_response.json()
                
                consumption_kwh = _calculate_device_consumption(hist_data)
                
                devices.append({
                    "entity_id": entity_id,
                    "device_name": device_name,
                    "consumption_kwh": consumption_kwh,
                    "period_hours": 24
                })
            
            # Sort by consumption (highest first)
            devices.sort(key=lambda x: x["consumption_kwh"], reverse=True)
            
            logger.info(f"Retrieved energy breakdown for {len(devices)} devices")
            return devices
            
    except Exception as e:
        logger.error(f"Failed to get device energy breakdown: {e}")
        return _get_mock_device_breakdown()


async def get_weekly_average_consumption() -> float:
    """
    Get average daily energy consumption over the past week.
    
    Returns:
        Average daily consumption in kWh
    """
    if not HA_TOKEN:
        logger.warning("HA_TOKEN not set, using mock data")
        return 25.0  # Mock: 25 kWh/day average
    
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{HA_BASE_URL}/api/history/period/{start_time.isoformat()}",
                headers={
                    "Authorization": f"Bearer {HA_TOKEN}",
                    "Content-Type": "application/json"
                },
                params={
                    "filter_entity_id": "sensor.energy_consumption",
                    "end_time": end_time.isoformat()
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if not data:
                logger.warning("No energy data for weekly average")
                return 25.0
            
            total_kwh = _calculate_total_consumption(data)
            daily_average = total_kwh / 7.0
            
            logger.info(f"Weekly average consumption: {daily_average:.2f} kWh/day")
            return daily_average
            
    except Exception as e:
        logger.error(f"Failed to get weekly average: {e}")
        return 25.0


def _calculate_total_consumption(history_data: List[List[Dict[str, Any]]]) -> float:
    """Calculate total consumption from history data"""
    if not history_data or not history_data[0]:
        return 0.0
    
    states = history_data[0]
    if len(states) < 2:
        return 0.0
    
    try:
        # Get first and last readings
        first_reading = float(states[0]["state"])
        last_reading = float(states[-1]["state"])
        
        # Consumption is the difference
        consumption = last_reading - first_reading
        return max(0.0, consumption)
    except (ValueError, KeyError, IndexError):
        return 0.0


def _calculate_device_consumption(history_data: List[List[Dict[str, Any]]]) -> float:
    """Calculate device consumption from history data"""
    return _calculate_total_consumption(history_data)


def _get_mock_energy_data() -> Dict[str, Any]:
    """Generate mock energy consumption data"""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    
    # Mock: 28 kWh for 24 hours
    return {
        "total_kwh": 28.5,
        "period_start": start_time.isoformat(),
        "period_end": end_time.isoformat(),
        "period_hours": 24,
        "source": "mock"
    }


def _get_mock_device_breakdown() -> List[Dict[str, Any]]:
    """Generate mock device energy breakdown"""
    return [
        {
            "entity_id": "sensor.hvac_energy",
            "device_name": "HVAC System",
            "consumption_kwh": 12.5,
            "period_hours": 24
        },
        {
            "entity_id": "sensor.water_heater_energy",
            "device_name": "Water Heater",
            "consumption_kwh": 6.3,
            "period_hours": 24
        },
        {
            "entity_id": "sensor.refrigerator_energy",
            "device_name": "Refrigerator",
            "consumption_kwh": 3.2,
            "period_hours": 24
        },
        {
            "entity_id": "sensor.washer_dryer_energy",
            "device_name": "Washer/Dryer",
            "consumption_kwh": 2.8,
            "period_hours": 24
        },
        {
            "entity_id": "sensor.lighting_energy",
            "device_name": "Lighting",
            "consumption_kwh": 2.1,
            "period_hours": 24
        },
        {
            "entity_id": "sensor.entertainment_energy",
            "device_name": "Entertainment System",
            "consumption_kwh": 1.6,
            "period_hours": 24
        }
    ]
