import os
from typing import Any, Optional

# Make composio imports optional - don't crash server if composio not installed
try:
    from composio.constants import DEFAULT_ENTITY_ID
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
    DEFAULT_ENTITY_ID = "default"

    # Stub exception classes for when composio isn't available
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

from letta.constants import COMPOSIO_ENTITY_ENV_VAR_KEY
from letta.functions.async_composio_toolset import AsyncComposioToolSet
from letta.utils import run_async_task


def check_composio_available():
    """Check if composio is available, raise clear error if not"""
    if not COMPOSIO_AVAILABLE:
        raise ImportError(
            "composio is not installed. Install with `pip install composio-core` "
            "or disable composio-backed tools."
        )


# TODO: This is kind of hacky, as this is used to search up the action later on composio's side
# TODO: So be very careful changing/removing these pair of functions
def _generate_func_name_from_composio_action(action_name: str) -> str:
    """
    Generates the composio function name from the composio action.

    Args:
        action_name: The composio action name

    Returns:
        function name
    """
    return action_name.lower()


def generate_composio_action_from_func_name(func_name: str) -> str:
    """
    Generates the composio action from the composio function name.

    Args:
        func_name: The composio function name

    Returns:
        composio action name
    """
    return func_name.upper()


def generate_composio_tool_wrapper(action_name: str) -> tuple[str, str]:
    check_composio_available()

    # Generate func name
    func_name = _generate_func_name_from_composio_action(action_name)

    wrapper_function_str = f"""\
def {func_name}(**kwargs):
    raise RuntimeError("Something went wrong - we should never be using the persisted source code for Composio. Please reach out to Letta team")
"""

    # Compile safety check
    _assert_code_gen_compilable(wrapper_function_str.strip())

    return func_name, wrapper_function_str.strip()


async def execute_composio_action_async(
    action_name: str, args: dict, api_key: Optional[str] = None, entity_id: Optional[str] = None
) -> tuple[str, str]:
    check_composio_available()

    entity_id = entity_id or os.getenv(COMPOSIO_ENTITY_ENV_VAR_KEY, DEFAULT_ENTITY_ID)
    composio_toolset = AsyncComposioToolSet(api_key=api_key, entity_id=entity_id, lock=False)
    try:
        response = await composio_toolset.execute_action(action=action_name, params=args)
    except ApiKeyNotProvidedError as e:
        raise RuntimeError(f"API key not provided or invalid for Composio action '{action_name}': {str(e)}")
    except ConnectedAccountNotFoundError as e:
        raise RuntimeError(f"Connected account not found for Composio action '{action_name}': {str(e)}")
    except EnumMetadataNotFound as e:
        raise RuntimeError(f"Enum metadata not found for Composio action '{action_name}': {str(e)}")
    except EnumStringNotFound as e:
        raise RuntimeError(f"Enum string not found for Composio action '{action_name}': {str(e)}")
    except ComposioSDKError as e:
        raise RuntimeError(f"Composio SDK error while executing action '{action_name}': {str(e)}")
    except Exception as e:
        print(type(e))
        raise RuntimeError(f"An unexpected error occurred in Composio SDK while executing action '{action_name}': {str(e)}")

    return str(response.get("successfull")), str(response.get("data"))


def execute_composio_action(action_name: str, args: dict, api_key: Optional[str] = None, entity_id: Optional[str] = None) -> tuple[str, str]:
    return run_async_task(execute_composio_action_async(action_name=action_name, args=args, api_key=api_key, entity_id=entity_id))


def _assert_code_gen_compilable(code: str):
    """
    Verifies that the code is compilable
    """
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        raise ValueError(f"Code compilation failed: {e}")
