    def load_last_function_response(self):
        """Load the last function response from message history - PATCHED for async/sync compatibility"""
        import asyncio
        try:
            result = self.agent_manager.get_in_context_messages(agent_id=self.agent_state.id, actor=self.user)
            # Handle async result
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    result.close()  # Clean up coroutine - we're in async context
                    return None
                except RuntimeError:
                    result = asyncio.run(result)
            if not result or not isinstance(result, list):
                return None
            for i in range(len(result) - 1, -1, -1):
                msg = result[i]
                if msg.role == MessageRole.tool and msg.content and len(msg.content) == 1 and isinstance(msg.content[0], TextContent):
                    text_content = msg.content[0].text
                    try:
                        response_json = json.loads(text_content)
                        if response_json.get("message"):
                            return response_json["message"]
                    except (json.JSONDecodeError, KeyError):
                        pass
        except Exception:
            pass
        return None
