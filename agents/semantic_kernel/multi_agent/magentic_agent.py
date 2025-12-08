import asyncio
import re

from semantic_kernel.agents import (
    ChatCompletionAgent,
    MagenticOrchestration,
    StandardMagenticManager,
    
    
)
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
from semantic_kernel.contents import ChatMessageContent
import logging
from agents.base_agent import BaseAgent  # adjust path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class Agent(BaseAgent):
    def __init__(self, state_store, session_id) -> None:
        super().__init__(state_store, session_id)
        self._agents = None
        self._mcp_plugin = None
        self._initialized = False
        self._customer_id = None

        # ✅ store past turns
        self._conversation_history: list[str] = []

        self._orchestration: MagenticOrchestration | None = None

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


        crm_billing = ChatCompletionAgent(
            service=AzureChatCompletion(deployment_name=self.azure_deployment),
            name="crm_billing",
            description="Query  CRM / billing systems for account, subscription, "
            "invoice, and payment information",
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
            plugins=[self._mcp_plugin],
        )

        product_promotions = ChatCompletionAgent(
            service=AzureChatCompletion(deployment_name=self.azure_deployment),
            name="product_promotions",
            description="Retrieve promotional offers, product availability, eligibility ",
            instructions="You are the Product & Promotions Agent.\n"
            "- Retrieve promotional offers, product availability, eligibility "
            "criteria, and discount information from structured sources.\n"
            "- For each response you **MUST** cross‑reference relevant *Knowledge Base* FAQs, terms & conditions, "
            "and best practices.\n"
            "- Provide factual, up‑to‑date product/promo details."
            "Only respond with data you retrieve using your tools.\n"
            "DO NOT respond to anything out of your domain.",
            plugins=[self._mcp_plugin],
        )

        security_authentication = ChatCompletionAgent(
            service=AzureChatCompletion(deployment_name=self.azure_deployment),
            name="security_authentication",
            description="Investigate authentication logs, account lockouts, and security incidents",
            instructions="You are the Security & Authentication Agent.\n"
            "- Investigate authentication logs, account lockouts, and security "
            "incidents in structured security databases.\n"
            "- For each response you **MUST** cross‑reference relevant *Knowledge Base* security policies and "
            "lockout troubleshooting guides.\n"
            "- Return clear risk assessments and recommended remediation steps."
            "Only respond with data you retrieve using your tools.\n"
            "DO NOT respond to anything out of your domain.",
            plugins=[self._mcp_plugin],
        )

        self._agents = [crm_billing, product_promotions, security_authentication ]
        self._initialized = True

        if self._orchestration is None:
            def agent_response_callback(message: ChatMessageContent) -> None:
                print(f"**{message.name}**\n{message.content}")

            self._orchestration = MagenticOrchestration(
                members=self._agents,
                manager=StandardMagenticManager(max_round_count=5, chat_completion_service=AzureChatCompletion(deployment_name=self.azure_deployment)),
                agent_response_callback=agent_response_callback,
            )

    def get_agents(self):
        if not self._initialized:
            raise RuntimeError("Call setup_agents() first!")
        return self._agents

    async def cleanup(self):
        if self._mcp_plugin:
            try:
                await self._mcp_plugin.close()
            except Exception:
                pass
        self._mcp_plugin = None
        self._initialized = False
        self._agents = None

    async def chat_async(self, user_input: str) -> str:
        match = re.search(r"customer\s*id[:\s]*([0-9]+)", user_input, re.IGNORECASE)
        if match:
            self._customer_id = match.group(1)

        if self._customer_id and "customer id" not in user_input.lower():
            user_input = f"Customer ID: {self._customer_id}\n{user_input}"

        await self.setup_agents()

        # ✅ Append new user input to the stored history
        self._conversation_history.append(f"User: {user_input}")

        # ✅ Combine whole history into a single task string
        task_text = "\n".join(self._conversation_history)

        runtime = InProcessRuntime()
        runtime.start()

        final_result = ""
        try:
            orchestration_result = await self._orchestration.invoke(
                task=task_text,
                runtime=runtime
            )
            final_result = await orchestration_result.get()
        except Exception as e:
            final_result = f"Error during orchestration: {e}"
        finally:
            await runtime.stop_when_idle()

        # ✅ Store assistant response in the history too
        self._conversation_history.append(f"Assistant: {final_result}")
        # # Fallback if orchestrator did not produce final answer
        # if not final_answer:
        #     final_answer = "Sorry, the team could not reach a conclusion within the allotted turns."



        # ✅ Also store for UI purposes if needed by your frontend
        self.append_to_chat_history([
            {"role": "user", "content": str (user_input)},
            {"role": "assistant", "content": str (final_result)},
        ])

        return str(final_result)


if __name__ == "__main__":

    async def _demo() -> None:
        dummy_state: dict = {}
        agent = Agent(dummy_state, session_id="demo")
        user_question = "My customer id is 101, why is my internet bill so high?"
        answer = await agent.chat_async(user_question)
        print("\n>>> Assistant reply:\n", answer)
        try:
            await agent.contoso_plugin.close()
        except Exception as exc:
            logger.warning(f"SSE plugin close failed: {exc}")

    asyncio.run(_demo())
