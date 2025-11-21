import asyncio
import logging
import re
from semantic_kernel.agents import (
    ChatCompletionAgent,
    GroupChatOrchestration,
    RoundRobinGroupChatManager,
    ChatHistoryAgentThread,
)
from fastapi.encoders import jsonable_encoder

from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
from semantic_kernel.contents import ChatMessageContent
from agents.base_agent import BaseAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class Agent(BaseAgent):
    def __init__(self, state_store, session_id) -> None:
        super().__init__(state_store, session_id)

        # Keys scoped by session_id to isolate data per user/session
        self.thread_key = f"{session_id}_thread"
        self.chat_history_key = f"{session_id}_chat_history"

        # Restore state from persistent store
        import inspect
        self._thread = self.state_store.get(self.thread_key)
        if isinstance(self._thread, dict):
            valid_keys = inspect.signature(ChatHistoryAgentThread).parameters.keys()
            filtered = {k: v for k, v in self._thread.items() if k in valid_keys}
            self._thread = ChatHistoryAgentThread(**filtered)
        self._conversation_history: list[dict] = self.state_store.get(self.chat_history_key, [])

        self._agents = None
        self._mcp_plugin = None
        self._initialized = False
        self._orchestration: GroupChatOrchestration | None = None

    async def setup_agents(self) -> None:
        if self._initialized:
            return

        self._mcp_plugin = MCPStreamableHttpPlugin(
            name="ContosoMCP",
            description="Contoso MCP Plugin",
            url=self.mcp_server_uri,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        await self._mcp_plugin.connect()

        primary_agent = ChatCompletionAgent(
            service=AzureChatCompletion(deployment_name=self.azure_deployment),
            name="PrimaryAgent",
            description="You are a helpful assistant answering customer questions for internet provider Contosso.",
            instructions=(
                "You are a helpful assistant. You can use multiple tools to find information and answer questions. "
                "Review the tools available to you and use them as needed. You can also ask clarifying questions if the user is not clear. "
                "If the user input is just an ID or feels incomplete as a question, **ALWAYS** review previous communication in the same session and **INFER** the user's intent based on the **most recent prior question or context—regardless of the topic (bill, promotions, security, etc.). "
                "For example, if the previous user question was about a bill, promotions, or security, and the user now provides an ID, assume they want information or action related to that topic for the provided ID. "
                "Be proactive in connecting the current input to the user's previous requests and always retain and use the previous context to inform your response. "
                "Provide the Secondary agent with both the complete context of the question (user query + previous history from the same session) and your answer for review."
            ),
            plugins=[self._mcp_plugin],
        )

        secondary_agent = ChatCompletionAgent(
            service=AzureChatCompletion(deployment_name=self.azure_deployment),
            name="SecondaryAgent",
            description="You are a supervisor assistant who the primary agent reports to before answering user",
            instructions=(
                "Provide constructive feedback. Respond with 'APPROVE' when your feedbacks are addressed."
            ),
            plugins=[self._mcp_plugin],
        )

        self._agents = [primary_agent, secondary_agent]
        self._initialized = True

        if self._orchestration is None:
            def agent_response_callback(message: ChatMessageContent) -> None:
                logger.info(f"**{message.name}**\n{message.content}")

            self._orchestration = GroupChatOrchestration(
                members=self._agents,
                manager=RoundRobinGroupChatManager(max_rounds=3),
                agent_response_callback=agent_response_callback,
            )

    async def chat_async(self, user_input: str) -> str:
        logger.info(f"[Session ID: {self.session_id}] Received user input: {user_input}")
        await self.setup_agents()

        # Prepare full conversation history for the agent
        from semantic_kernel.contents import ChatMessageContent
        messages = []
        for msg in self._conversation_history:
            messages.append(ChatMessageContent(role=msg["role"], content=msg["content"]))
        messages.append(ChatMessageContent(role="user", content=user_input))

        # Get response from primary agent, passing full conversation history and persistent thread
        response = await self._agents[0].get_response(messages=messages, thread=self._thread)

        # Update thread and persist
        self._thread = response.thread
        if self._thread:
            self.state_store[self.thread_key] = jsonable_encoder(self._thread)

        response_content = str(response.content)

        # Update and persist conversation history for UI
        self._conversation_history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response_content},
        ])
        self.state_store[self.chat_history_key] = self._conversation_history

        logger.info(f"[Session ID: {self.session_id}] Responded with: {response_content}")
        return response_content
