# /app/letta/helpers/message_helper_compat.py (overlay file)
# Compatibility wrapper for convert_message_creates_to_messages across Letta versions.
# Fixes TypeError in 0.13.0 where run_id became required but agent.py doesn't pass it.

from inspect import signature
import uuid

# Import the actual implementation shipped by Letta
from letta.helpers.message_helper import convert_message_creates_to_messages as _impl


def convert_message_creates_to_messages_compat(
    message_creates,
    agent_id: str,
    timezone: str,
    run_id: str | None = None,
    wrap_user_message: bool = True,
    wrap_system_message: bool = True,
):
    """
    Compatibility wrapper for convert_message_creates_to_messages across Letta versions.

    - If _impl requires run_id, supply one if missing (auto-generate UUID).
    - If _impl does not have run_id, call with the older parameter list.
    - Handles 3 signature variants: 3-arg, 5-arg, 6-arg.

    This allows agent.py to work without modification across Letta versions.
    """
    params = list(signature(_impl).parameters.keys())

    # Modern version (0.13.0+): requires run_id
    if "run_id" in params:
        if run_id is None:
            run_id = str(uuid.uuid4())
        return _impl(
            message_creates,
            agent_id,
            timezone,
            run_id,
            wrap_user_message,
            wrap_system_message,
        )

    # Mid-version: has wrap flags but no run_id
    if "wrap_user_message" in params and "wrap_system_message" in params:
        return _impl(
            message_creates,
            agent_id,
            timezone,
            wrap_user_message,
            wrap_system_message,
        )

    # Very old builds: just 3 args
    return _impl(message_creates, agent_id, timezone)
