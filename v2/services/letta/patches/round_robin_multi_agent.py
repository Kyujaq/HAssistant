import asyncio
from typing import AsyncGenerator, List, Optional

from letta.agent import Agent
from letta.agents.base_agent import BaseAgent
from letta.interface import AgentInterface
from letta.orm import User
from letta.schemas.agent import AgentState
from letta.schemas.enums import MessageStreamStatus
from letta.schemas.letta_message_content import TextContent
from letta.schemas.message import Message, MessageCreate
from letta.schemas.openai.chat_completion_response import UsageStatistics
from letta.schemas.usage import LettaUsageStatistics
from letta.services.agent_manager import AgentManager
from letta.services.message_manager import MessageManager
from letta.services.block_manager import BlockManager

# Import our async collection utility
from letta.groups._group_stream_utils import collect_async


class RoundRobinMultiAgent(BaseAgent):
    def __init__(
        self,
        interface: AgentInterface,
        agent_state: AgentState,
        user: User,
        # custom
        group_id: str = "",
        agent_ids: List[str] = [],
        description: str = "",
        max_turns: Optional[int] = None,
    ):
        super().__init__(
            agent_id=agent_state.id,
            openai_client=getattr(interface, 'openai_client', None) if interface else None,
            message_manager=MessageManager(),
            agent_manager=AgentManager(),
            actor=user,
        )
        self.interface = interface
        self.agent_state = agent_state
        self.user = user
        self.block_manager = BlockManager()
        self.group_id = group_id
        self.agent_ids = agent_ids
        self.description = description
        self.max_turns = max_turns or len(agent_ids)

    async def step_stream(
        self,
        input_messages: List[MessageCreate],
        max_steps: int = 0,
    ) -> AsyncGenerator[MessageStreamStatus, None]:
        """Proper async streaming implementation for groups."""
        # Delegate to the synchronous step method for now
        # In a full implementation, you'd yield incremental events
        try:
            usage_stats = self.step(input_messages=input_messages)
            # Yield final completion event
            yield MessageStreamStatus(
                status="done",
                usage=usage_stats if hasattr(usage_stats, 'model_dump') else None
            )
        except Exception as e:
            yield MessageStreamStatus(status="error", error=str(e))

    def step(
        self,
        input_messages: List[MessageCreate],
        chaining: bool = True,
        max_chaining_steps: Optional[int] = None,
        put_inner_thoughts_first: bool = True,
        **kwargs,
    ) -> LettaUsageStatistics:
        total_usage = UsageStatistics()
        step_count = 0
        speaker_id = None

        # Load settings
        token_streaming = self.interface.streaming_mode if hasattr(self.interface, "streaming_mode") else False
        metadata = self.interface.metadata if hasattr(self.interface, "metadata") else None

        # Load agents and initialize chat history with indexing
        agents, message_index = {}, {}
        chat_history: List[MessageCreate] = []
        for agent_id in self.agent_ids:
            agents[agent_id] = self.load_participant_agent(agent_id=agent_id)
            message_index[agent_id] = 0

        # Prepare new messages
        new_messages = []
        for message in input_messages:
            if isinstance(message.content, str):
                message.content = [TextContent(text=message.content)]
            message.group_id = self.group_id
            new_messages.append(message)

        try:
            for i in range(self.max_turns):
                # Select speaker
                speaker_id = self.agent_ids[i % len(self.agent_ids)]

                # Update chat history
                chat_history.extend(new_messages)

                # Perform participant step
                participant_agent = agents[speaker_id]
                usage_stats = participant_agent.step(
                    input_messages=chat_history[message_index[speaker_id] :],
                    chaining=chaining,
                    max_chaining_steps=max_chaining_steps,
                    stream=token_streaming,
                    skip_verify=True,
                    metadata=metadata,
                    put_inner_thoughts_first=put_inner_thoughts_first,
                )

                # Parse participant response
                responses = Message.to_letta_messages_from_list(participant_agent.last_response_messages)
                assistant_messages = [response for response in responses if response.message_type == "assistant_message"]
                new_messages = [
                    MessageCreate(
                        role="system",
                        content=[TextContent(text=message.content)] if isinstance(message.content, str) else message.content,
                        name=participant_agent.agent_state.name,
                        otid=message.otid,
                        sender_id=participant_agent.agent_state.id,
                        group_id=self.group_id,
                    )
                    for message in assistant_messages
                ]

                # Update message index
                message_index[speaker_id] = len(chat_history) + len(new_messages)

                # Sum usage
                total_usage.prompt_tokens += usage_stats.prompt_tokens
                total_usage.completion_tokens += usage_stats.completion_tokens
                total_usage.total_tokens += usage_stats.total_tokens
                step_count += 1

            # Persist remaining chat history
            chat_history.extend(new_messages)
            for agent_id, index in message_index.items():
                if agent_id == speaker_id:
                    continue
                messages_to_persist = []
                for message in chat_history[index:]:
                    message_to_persist = Message(
                        role=message.role,
                        content=message.content,
                        name=message.name,
                        otid=message.otid,
                        sender_id=message.sender_id,
                        group_id=self.group_id,
                        agent_id=agent_id,
                    )
                    messages_to_persist.append(message_to_persist)
                self.message_manager.create_many_messages(messages_to_persist, actor=self.user)

        except Exception as e:
            raise e
        finally:
            self.interface.step_yield()

        self.interface.step_complete()

        return LettaUsageStatistics(**total_usage.model_dump(), step_count=step_count)

    def load_participant_agent(self, agent_id: str) -> Agent:
        agent_state = asyncio.run(
            self.agent_manager.get_agent_by_id_async(agent_id=agent_id, actor=self.user)
        )
        persona_block = agent_state.memory.get_block(label="persona")

        # Shortened group chat context to avoid exceeding character limits
        group_chat_participant_persona = (
            f"\n[GROUP: {len(self.agent_ids)} participants. "
            f"{self.description}. Stay in character, be concise.]"
        )

        # Calculate new value and ensure it doesn't exceed the block's limit
        new_value = persona_block.value + group_chat_participant_persona
        if hasattr(persona_block, 'limit') and persona_block.limit:
            if len(new_value) > persona_block.limit:
                # Truncate the group context to fit
                available_space = persona_block.limit - len(persona_block.value) - 10  # 10 char buffer
                if available_space > 20:  # Only add if we have reasonable space
                    group_chat_participant_persona = f"\n[GROUP: {len(self.agent_ids)} participants.]"
                    new_value = persona_block.value + group_chat_participant_persona
                else:
                    # Skip adding group context if no space
                    new_value = persona_block.value

        agent_state.memory.update_block_value(label="persona", value=new_value)
        return Agent(
            agent_state=agent_state,
            interface=self.interface,
            user=self.user,
            save_last_response=True,
        )
