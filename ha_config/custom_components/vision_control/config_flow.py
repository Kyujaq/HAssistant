"""Config flow for Vision Control integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VisionControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vision Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Create the entry
            return self.async_create_entry(
                title="Vision Control",
                data=user_input,
            )

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "description": "Enable AI-powered vision control for screen interaction."
            },
        )
