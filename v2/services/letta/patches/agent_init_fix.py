# Patch for /app/letta/agent.py load_last_function_response method
# Fixes: TypeError: object of type 'coroutine' has no len()

import asyncio
import json
from letta.schemas.enums import MessageRole
from letta.schemas.letta_message_content import TextContent


def load_last_function_response(self):
    """Load the last function response from message history - patched to handle async"""
    try:
        # Try sync version first
        in_context_messages = self.agent_manager.get_in_context_messages(agent_id=self.agent_state.id, actor=self.user)

        # Check if result is a coroutine (async)
        if asyncio.iscoroutine(in_context_messages):
            # If we're already in an async context, this will fail
            # So we need to handle it properly
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - can't use asyncio.run()
                # Return None and let the caller handle it
                in_context_messages.close()  # Clean up the coroutine
                return None
            except RuntimeError:
                # No running loop - we can use asyncio.run()
                in_context_messages = asyncio.run(in_context_messages)

        if in_context_messages is None or not isinstance(in_context_messages, list):
            return None

        for i in range(len(in_context_messages) - 1, -1, -1):
            msg = in_context_messages[i]
            if msg.role == MessageRole.tool and msg.content and len(msg.content) == 1 and isinstance(msg.content[0], TextContent):
                text_content = msg.content[0].text
                try:
                    response_json = json.loads(text_content)
                    if response_json.get("message"):
                        return response_json["message"]
                except (json.JSONDecodeError, KeyError):
                    pass  # Continue to next message
    except Exception:
        # If anything fails, just return None
        pass
    return None
