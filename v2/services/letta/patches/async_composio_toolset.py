import json
from typing import Any

import aiohttp

# Make composio imports optional
try:
    from composio import ComposioToolSet as BaseComposioToolSet
    from composio.exceptions import (
        ApiKeyNotProvidedError,
        ComposioSDKError,
        ConnectedAccountNotFoundError,
        EnumMetadataNotFound,
        EnumStringNotFound,
    )
    COMPOSIO_AVAILABLE = True
except ImportError:
    COMPOSIO_AVAILABLE = False
    # Create stub base class
    class BaseComposioToolSet:
        def __init__(self, *args, **kwargs):
            pass

    # Stub exceptions
    class ApiKeyNotProvidedError(Exception):
        pass

    class ComposioSDKError(Exception):
        pass

    class ConnectedAccountNotFoundError(Exception):
        pass

    class EnumMetadataNotFound(Exception):
        pass

    class EnumStringNotFound(Exception):
        pass


def check_composio_available():
    """Check if composio is available"""
    if not COMPOSIO_AVAILABLE:
        raise ImportError(
            "composio is not installed. Install with `pip install composio-core` "
            "or disable composio-backed tools."
        )


class AsyncComposioToolSet(BaseComposioToolSet):
    """
    Async version of ComposioToolSet client for interacting with Composio API
    Used to asynchronously hit the execute action endpoint

    https://docs.composio.dev/api-reference/api-reference/v3/tools/post-api-v-3-tools-execute-action
    """

    def __init__(self, api_key: str, entity_id: str, lock: bool = True):
        """
        Initialize the AsyncComposioToolSet client

        Args:
            api_key (str): Your Composio API key
            entity_id (str): Your Composio entity ID
            lock (bool): Whether to use locking (default: True)
        """
        check_composio_available()
        super().__init__(api_key=api_key, entity_id=entity_id, lock=lock)

        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self._api_key,
        }

    async def execute_action(
        self,
        action: str,
        params: dict[str, Any] = {},
    ) -> dict[str, Any]:
        """
        Execute an action asynchronously using the Composio API

        Args:
            action (str): The name of the action to execute
            params (dict[str, Any], optional): Parameters for the action

        Returns:
            dict[str, Any]: The API response

        Raises:
            ApiKeyNotProvidedError: if the API key is not provided
            ComposioSDKError: if a general Composio SDK error occurs
            ConnectedAccountNotFoundError: if the connected account is not found
            EnumMetadataNotFound: if enum metadata is not found
            EnumStringNotFound: if enum string is not found
            aiohttp.ClientError: if a network-related error occurs
        """
        check_composio_available()

        url = "https://backend.composio.dev/api/v3/tools/execute_action"
        payload = {
            "action": action,
            "params": params,
            "entity_id": self._entity_id,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise ApiKeyNotProvidedError(f"Invalid API key: {e}")
            elif e.status == 404:
                if "entity" in str(e).lower():
                    raise ConnectedAccountNotFoundError(f"Connected account not found: {e}")
                else:
                    raise ComposioSDKError(f"Resource not found: {e}")
            else:
                raise ComposioSDKError(f"API error: {e}")
        except aiohttp.ClientError as e:
            raise ComposioSDKError(f"Network error: {e}")
