"""AI Task entity for Vision Control."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.components.ai_task import (
    AITaskEntity,
    AITaskEntityFeature,
    GenDataTask,
    GenDataTaskResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

VISION_GATEWAY_URL = "http://vision-gateway:8088"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vision Control AI Task from a config entry."""
    async_add_entities([VisionControlAITask()])


class VisionControlAITask(AITaskEntity):
    """AI Task entity for vision-based screen control."""

    _attr_name = "Vision Control"
    _attr_unique_id = "vision_control_ai_task"
    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    async def _async_generate_data(
        self, task: GenDataTask, chat_log: Any
    ) -> GenDataTaskResult:
        """Generate data based on vision analysis.

        This method analyzes the screen using vision-gateway and returns
        structured data about UI elements that can be interacted with.
        """
        _LOGGER.info(f"Vision Control AI Task called with instructions: {task.instructions}")

        try:
            # Get latest frame from vision-gateway
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{VISION_GATEWAY_URL}/api/latest_frame/hdmi",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        error_msg = f"Vision gateway returned {response.status}"
                        _LOGGER.error(error_msg)
                        return GenDataTaskResult(
                            conversation_id=chat_log.conversation_id if hasattr(chat_log, 'conversation_id') else None,
                            data={"error": error_msg, "success": False}
                        )

                    frame_data = await response.json()

            # TODO: For now, return frame availability
            # When K80 arrives, this will do object detection and return element coordinates
            result_data = {
                "success": True,
                "frame_available": "image" in frame_data,
                "timestamp": frame_data.get("timestamp"),
                "source": frame_data.get("source"),
                "message": "Vision gateway connected. K80 preprocessing will enable element detection.",
                "instructions_received": task.instructions
            }

            _LOGGER.info(f"Vision analysis result: {result_data}")

            return GenDataTaskResult(
                conversation_id=chat_log.conversation_id if hasattr(chat_log, 'conversation_id') else None,
                data=result_data
            )

        except Exception as e:
            _LOGGER.error(f"Error in vision control AI task: {e}", exc_info=True)
            return GenDataTaskResult(
                conversation_id=chat_log.conversation_id if hasattr(chat_log, 'conversation_id') else None,
                data={"error": str(e), "success": False}
            )
