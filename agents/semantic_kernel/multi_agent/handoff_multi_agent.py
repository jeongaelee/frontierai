import logging

from agents.base_agent import BaseAgent
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
from fastapi.encoders import jsonable_encoder
# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Agent(BaseAgent):
    def __init__(self, state_store, session_id) -> None:
        super().__init__(state_store, session_id)
        self._agent = None
        self._initialized = False
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

    async def _setup_agents(self) -> None:
        """Initialize the assistant and tools only once."""
        if self._initialized:
            return

        service = AzureChatCompletion(
            api_key=self.azure_openai_key,
            endpoint=self.azure_openai_endpoint,
            api_version=self.api_version,
            deployment_name=self.azure_deployment,
        )

        # Set up the SSE plugin for the MCP service.
        contoso_plugin = MCPStreamableHttpPlugin(
            name="ContosoMCP",
            description="Contoso MCP Plugin",
            url=self.mcp_server_uri,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        # Open the SSE connection so tools/prompts are loaded
        await contoso_plugin.connect()

        # Define compete agents and use them to create the main agent.
        crm_billing = ChatCompletionAgent(
            service=service,
            name="crm_billing",
            instructions="You are the CRM & Billing Agent.\n"
            "- Query structured CRM / billing systems for account, subscription, "
            "invoice, and payment information as needed.\n"
            "- For each response you **MUST** cross‑reference relevant *Knowledge Base* articles on billing policies, payment "
            "processing, refund rules, etc., to ensure responses are accurate "
            "and policy‑compliant.\n"
            "- Reply with concise, structured information and flag any policy "
            "concerns you detect.\n"
            "Only respond with data you retrieve using your tools.\n"
            "DO NOT respond to anything out of your domain.",
            plugins=[contoso_plugin],
        )

        product_promotions = ChatCompletionAgent(
            service=service,
            name="product_promotions",
            instructions="You are the Product & Promotions Agent.\n"
            "- Retrieve promotional offers, product availability, eligibility "
            "criteria, and discount information from structured sources.\n"
            "- For each response you **MUST** cross‑reference relevant *Knowledge Base* FAQs, terms & conditions, "
            "and best practices.\n"
            "- Provide factual, up‑to‑date product/promo details."
            "Only respond with data you retrieve using your tools.\n"
            "DO NOT respond to anything out of your domain.",
            plugins=[contoso_plugin],
        )

        security_authentication = ChatCompletionAgent(
            service=service,
            name="security_authentication",
            instructions="You are the Security & Authentication Agent.\n"
            "- Investigate authentication logs, account lockouts, and security "
            "incidents in structured security databases.\n"
            "- For each response you **MUST** cross‑reference relevant *Knowledge Base* security policies and "
            "lockout troubleshooting guides.\n"
            "- Return clear risk assessments and recommended remediation steps."
            "Only respond with data you retrieve using your tools.\n"
            "DO NOT respond to anything out of your domain.",
            plugins=[contoso_plugin],
        )

        self._agent = ChatCompletionAgent(
            service=service,
            name="triage_agent",
            instructions=(
                 "Handoff to the appropriate agent based on the language of the request."
                "if you need clarification or info is not complete ask follow-up Qs"
                "Like if customer asks questions without providing any identifying info such as customer ID, ask for it"
            ),
            plugins=[crm_billing, product_promotions, security_authentication],
        )

        # Create a thread to hold the conversation.
        self._thread: ChatHistoryAgentThread | None = None
        # Re‑create the thread from persisted state (if any)
        if self.state and isinstance(self.state, dict) and "thread" in self.state:
            try:
                self._thread = self.state["thread"]
                logger.info("Restored thread from SESSION_STORE")
            except Exception as e:
                logger.warning(f"Could not restore thread: {e}")

        self._initialized = True

    async def chat_async(self, user_input: str) -> str:
        logger.info(f"[Session ID: {self.session_id}] Received user input: {user_input}")
        await self._setup_agents()

        # Prepare full conversation history for the agent
        from semantic_kernel.contents import ChatMessageContent
        messages = []
        for msg in self._conversation_history:
            messages.append(ChatMessageContent(role=msg["role"], content=msg["content"]))
        messages.append(ChatMessageContent(role="user", content=user_input))

        # Get response from main agent, passing full conversation history and persistent thread
        response = await self._agent.get_response(messages=messages, thread=self._thread)
        response_content = str(response.content)

        # Update thread and persist
        self._thread = response.thread
        if self._thread:
            self.state_store[self.thread_key] = jsonable_encoder(self._thread)

        # Update and persist conversation history for UI
        self._conversation_history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response_content},
        ])
        self.state_store[self.chat_history_key] = self._conversation_history

        logger.info(f"[Session ID: {self.session_id}] Responded with: {response_content}")
        return response_content
