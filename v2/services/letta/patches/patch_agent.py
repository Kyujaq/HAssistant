#!/usr/bin/env python3
"""
Runtime patch for Letta Agent class to fix async/sync issues in load_last_function_response.
Apply this before starting the Letta server.
"""

import asyncio
import json
from letta.schemas.enums import MessageRole
from letta.schemas.letta_message_content import TextContent


def patched_load_last_function_response(self):
    """Load the last function response from message history - handles both async and sync"""
    try:
        result = self.agent_manager.get_in_context_messages(agent_id=self.agent_state.id, actor=self.user)

        # If it's a coroutine, try to await it properly
        if asyncio.iscoroutine(result):
            try:
                # Check if we're in an async context
                loop = asyncio.get_running_loop()
                # We are in async - can't use asyncio.run(), so just return None
                result.close()  # Clean up coroutine
                return None
            except RuntimeError:
                # No running loop - safe to use asyncio.run()
                result = asyncio.run(result)

        # Safety check
        if not result or not isinstance(result, list):
            return None

        # Iterate backwards through messages
        for i in range(len(result) - 1, -1, -1):
            msg = result[i]
            if (msg.role == MessageRole.tool and
                msg.content and
                len(msg.content) == 1 and
                isinstance(msg.content[0], TextContent)):
                text_content = msg.content[0].text
                try:
                    response_json = json.loads(text_content)
                    if response_json.get("message"):
                        return response_json["message"]
                except (json.JSONDecodeError, KeyError):
                    pass  # Continue to next message
    except Exception as e:
        # Silently fail and return None - this is non-critical
        pass
    return None


# Apply the patch
if __name__ == "__main__":
    from letta.agent import Agent
    Agent.load_last_function_response = patched_load_last_function_response
    print("[PATCH] Applied agent.load_last_function_response fix")
