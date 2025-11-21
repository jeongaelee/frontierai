"""
Optimized handoff pattern for domain-based multi-agent routing.

Architecture:
1. User chats directly with the assigned specialist agent (no middleman)
2. Lightweight intent classifier checks for domain changes
3. Only re-routes when user switches topics or requests help
4. Full streaming visibility via WebSocket

Key improvements over v2:
- No heavy Magentic orchestrator
- Direct agent-to-user communication
- Efficient intent detection using vanilla LLM calls
- Simple state management for current agent tracking
"""

import json
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from agent_framework import ChatAgent, ChatMessage, Role, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient

from agents.base_agent import BaseAgent
from agents.agent_framework.utils import create_filtered_tool_list

logger = logging.getLogger(__name__)


# Pydantic model for structured intent classification output
class IntentClassification(BaseModel):
    """Structured output for intent classification."""
    domain: str = Field(
        description="Target domain: crm_billing, product_promotions, or security_authentication"
    )
    is_domain_change: bool = Field(
        description="Whether this represents a change from the current domain"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )
    reasoning: str = Field(
        description="Brief explanation of the classification decision"
    )


# Domain definitions
DOMAINS = {
    "crm_billing": {
        "name": "CRM & Billing Specialist",
        "description": "Handles subscriptions, billing, invoices, payments, and account adjustments",
        "tools": [
            "get_all_customers",
            "get_customer_detail",
            "get_subscription_detail",
            "get_billing_summary",
            "get_invoice_payments",
            "pay_invoice",
            "get_data_usage",
            "update_subscription",
            "search_knowledge_base",
        ],
        "instructions": (
            "You are the CRM & Billing Specialist for Contoso support.\n\n"
            "**Your expertise:**\n"
            "- Customer accounts, subscriptions, billing, invoices, payments\n"
            "- Account adjustments, data usage, subscription updates\n\n"
            "**Critical rules:**\n"
            "- ALWAYS use your tools to retrieve factual data. NEVER guess or hallucinate.\n"
            "- If customer info is needed but not provided, ask the user directly for it.\n"
            "- If the user asks about products, promotions, or security issues, you MUST respond with this EXACT phrase: "
            "'This is outside my area. Let me connect you with the right specialist.'\n"
            "- Be concise and professional. Provide specific details from tool responses.\n"
        ),
    },
    "product_promotions": {
        "name": "Product & Promotions Specialist",
        "description": "Handles product inquiries, plan changes, promotions, and eligibility",
        "tools": [
            "get_products",
            "get_product_detail",
            "get_promotions",
            "get_eligible_promotions",
            "get_customer_orders",
            "search_knowledge_base",
        ],
        "instructions": (
            "You are the Product & Promotions Specialist for Contoso support.\n\n"
            "**Your expertise:**\n"
            "- Product catalog, features, availability\n"
            "- Promotions, discounts, eligibility rules\n"
            "- Customer orders and product recommendations\n\n"
            "**Critical rules:**\n"
            "- ALWAYS use your tools to retrieve factual data. NEVER guess or hallucinate.\n"
            "- If the user asks about billing or security issues, you MUST respond with this EXACT phrase: "
            "'This is outside my area. Let me connect you with the right specialist.'\n"
            "- Be enthusiastic and helpful. Highlight benefits and savings opportunities.\n"
        ),
    },
    "security_authentication": {
        "name": "Security & Authentication Specialist",
        "description": "Handles authentication failures, lockouts, security incidents, and remediation",
        "tools": [
            "get_security_logs",
            "unlock_account",
            "get_support_tickets",
            "create_support_ticket",
            "search_knowledge_base",
        ],
        "instructions": (
            "You are the Security & Authentication Specialist for Contoso support.\n\n"
            "**Your expertise:**\n"
            "- Account security, authentication issues, lockouts\n"
            "- Security logs, incident investigation, remediation\n"
            "- Support ticket management for security issues\n\n"
            "**Critical rules:**\n"
            "- ALWAYS use your tools to retrieve factual data. NEVER guess or hallucinate.\n"
            "- If the user asks about billing or products, you MUST respond with this EXACT phrase: "
            "'This is outside my area. Let me connect you with the right specialist.'\n"
            "- Take security seriously. Verify user identity and flag suspicious activity.\n"
        ),
    },
}

# Intent classification prompt
INTENT_CLASSIFIER_PROMPT = """You are an intent classifier for Contoso customer support.

Available domains:
1. crm_billing: subscriptions, billing, invoices, payments, account adjustments
2. product_promotions: products, plans, promotions, eligibility, orders
3. security_authentication: security issues, lockouts, authentication failures

Analyze the user's message and determine:
1. Which domain it belongs to
2. Whether it's a domain change from the current context

Current domain: {current_domain}
User message: {user_message}

Respond with JSON:
{{
    "domain": "crm_billing|product_promotions|security_authentication",
    "is_domain_change": true|false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Rules:
- If uncertain, default to current domain with low confidence
- Detect explicit requests to "talk to someone else" or "get help with X" as domain changes
- Consider context: billing questions stay in billing unless user explicitly changes topic
"""


class Agent(BaseAgent):
    """
    Optimized handoff pattern using vanilla workflow and direct agent communication.
    
    Flow:
    1. Intent classifier determines which domain specialist to route to
    2. User communicates directly with assigned specialist
    3. On domain change detection, seamlessly transfer to new specialist
    4. Specialists have filtered tool access and clear boundaries
    """

    def __init__(self, state_store: Dict[str, Any], session_id: str, access_token: str | None = None) -> None:
        super().__init__(state_store, session_id)
        self._access_token = access_token
        self._ws_manager = None
        
        # Track current agent and conversation history per domain
        self._current_domain = state_store.get(f"{session_id}_current_domain", None)
        self._domain_agents: Dict[str, ChatAgent] = {}
        self._domain_threads: Dict[str, Any] = {}
        self._initialized = False
        
        # Turn tracking for tool grouping
        self._turn_key = f"{session_id}_handoff_turn"
        self._current_turn = state_store.get(self._turn_key, 0)
        
        # Context transfer configuration: -1 = all history, 0 = none, N = last N turns
        self._context_transfer_turns = int(os.getenv("HANDOFF_CONTEXT_TRANSFER_TURNS", "-1"))
        
        # Lazy classification configuration
        self._lazy_classification = os.getenv("HANDOFF_LAZY_CLASSIFICATION", "true").lower() == "true"
        self._default_domain = os.getenv("HANDOFF_DEFAULT_DOMAIN", "crm_billing")
        
        logger.info(
            f"[HANDOFF] Configuration: lazy_classification={self._lazy_classification}, "
            f"default_domain={self._default_domain}, context_transfer_turns={self._context_transfer_turns}"
        )

    def _detect_handoff_request(self, response_text: str) -> bool:
        """
        Detect if the agent response contains a handoff request using pattern matching.
        
        This avoids the need for LLM-based detection by looking for key phrases that
        agents are instructed to use when a request is outside their domain.
        
        Args:
            response_text: The agent's response text
            
        Returns:
            True if handoff is requested, False otherwise
        """
        # Normalize text for matching
        normalized = response_text.lower()
        
        # Define handoff patterns (in order of specificity)
        handoff_patterns = [
            r"outside my area.*connect you with.*specialist",  # Exact template match
            r"outside my (domain|expertise|area)",  # Domain boundary indication
            r"connect you with.*specialist",  # Explicit handoff language
            r"let me (transfer|route|connect) you",  # Transfer language
            r"not my (specialty|expertise|domain)",  # Boundary indication
            r"better suited to help",  # Redirection language
        ]
        
        # Check each pattern
        for pattern in handoff_patterns:
            if re.search(pattern, normalized):
                logger.info(f"[HANDOFF] Detected handoff request with pattern: {pattern}")

                return True
        
        # Additional keyword-based detection with proximity check
        keywords_group1 = ["outside", "not my"]
        keywords_group2 = ["area", "domain", "expertise", "specialty"]
        keywords_group3 = ["connect", "transfer", "specialist", "help"]
        
        # Check if keywords from different groups appear within reasonable distance (100 chars)
        for kw1 in keywords_group1:
            if kw1 in normalized:
                start_pos = normalized.find(kw1)
                window = normalized[start_pos:start_pos + 100]
                
                has_group2 = any(kw2 in window for kw2 in keywords_group2)
                has_group3 = any(kw3 in window for kw3 in keywords_group3)
                
                if has_group2 and has_group3:
                    logger.info(f"[HANDOFF] Detected handoff via keyword proximity: {kw1} + groups 2&3")

                    return True
        return False

    def set_websocket_manager(self, manager: Any) -> None:
        """Allow backend to inject WebSocket manager for streaming events."""
        self._ws_manager = manager
        logger.info(f"[HANDOFF] WebSocket manager set for handoff agent, session_id={self.session_id}")

    async def _setup_agents(self) -> None:
        """Initialize all domain specialist agents with filtered MCP tools."""
        if self._initialized:
            return

        if not all([self.azure_openai_key, self.azure_deployment, self.azure_openai_endpoint, self.api_version]):
            raise RuntimeError(
                "Azure OpenAI configuration is incomplete. Ensure AZURE_OPENAI_API_KEY, "
                "AZURE_OPENAI_CHAT_DEPLOYMENT, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_API_VERSION are set."
            )

        headers = self._build_headers()
        base_mcp_tool = await self._create_mcp_tool(headers)

        # Connect to MCP server once to load all available tools
        if base_mcp_tool:
            await base_mcp_tool.__aenter__()
            logger.info(f"[HANDOFF] Connected to MCP server, loaded {len(base_mcp_tool.functions)} tools")

        chat_client = AzureOpenAIChatClient(
            api_key=self.azure_openai_key,
            deployment_name=self.azure_deployment,
            endpoint=self.azure_openai_endpoint,
            api_version=self.api_version,
        )

        # Create all domain specialist agents with filtered tools
        for domain_id, domain_config in DOMAINS.items():
            # Create filtered tool list for this domain using common utility
            domain_tools = create_filtered_tool_list(
                base_mcp_tool=base_mcp_tool,
                allowed_tool_names=domain_config["tools"],
                agent_name=domain_id
            )
            
            agent = ChatAgent(
                name=domain_id,
                chat_client=chat_client,
                instructions=domain_config["instructions"],
                tools=domain_tools,  # Pass list of filtered AIFunction objects
                model=self.openai_model_name,
            )
            
            # Enter agent context
            await agent.__aenter__()
            self._domain_agents[domain_id] = agent
            
            # Create or restore thread for this domain
            thread_state_key = f"{self.session_id}_thread_{domain_id}"
            thread_state = self.state_store.get(thread_state_key)
            
            if thread_state:
                self._domain_threads[domain_id] = await agent.deserialize_thread(thread_state)
            else:
                self._domain_threads[domain_id] = agent.get_new_thread()

        self._initialized = True
        logger.info(f"[HANDOFF] Initialized {len(self._domain_agents)} domain specialists with filtered tools")

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _create_mcp_tool(self, headers: Dict[str, str]) -> MCPStreamableHTTPTool | None:
        """
        Create the base MCP tool that will be shared across all domain specialists.
        
        The tool will be connected once and then filtered for each domain.
        
        Returns:
            MCPStreamableHTTPTool instance or None if MCP server is not configured
        """
        if not self.mcp_server_uri:
            logger.warning("MCP_SERVER_URI is not configured; agents will run without MCP tools.")
            return None

        tool = MCPStreamableHTTPTool(
            name="mcp-streamable",
            url=self.mcp_server_uri,
            headers=headers,
            timeout=30,
            request_timeout=30,
        )
        
        return tool

    async def _build_context_prefix(self, from_domain: str, to_domain: str) -> str | None:
        """
        Build a context prefix to prepend to the user's prompt on handoff.
        
        Args:
            from_domain: Previous domain specialist
            to_domain: New domain specialist
            
        Returns:
            Context prefix string or None if no context to transfer
        """
        if self._context_transfer_turns == 0:
            logger.info(f"[HANDOFF] Context transfer disabled (HANDOFF_CONTEXT_TRANSFER_TURNS=0)")
            return None
            
        # Get chat history
        history = self.chat_history
        if not history:
            logger.info(f"[HANDOFF] No chat history to transfer")
            return None
        
        # Determine how much history to transfer
        if self._context_transfer_turns == -1:
            # Transfer all history
            context_messages = history
            logger.info(f"[HANDOFF] Transferring all {len(history)} messages to {to_domain}")
        else:
            # Transfer last N turns (each turn = user + assistant pair)
            turns_to_transfer = self._context_transfer_turns * 2  # Each turn has 2 messages
            context_messages = history[-turns_to_transfer:] if len(history) > turns_to_transfer else history
            logger.info(f"[HANDOFF] Transferring last {self._context_transfer_turns} turns ({len(context_messages)} messages) to {to_domain}")
        
        # Build context summary
        context_parts = []
        for msg in context_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                context_parts.append(f"User: {content}")
            elif role == "assistant":
                context_parts.append(f"Previous Specialist: {content}")
        
        context_summary = "\n".join(context_parts)
        
        # Build context prefix
        context_prefix = (
            f"[CONTEXT FROM PREVIOUS CONVERSATION]\n"
            f"The user was previously speaking with the {DOMAINS[from_domain]['name']}.\n"
            f"Here is the recent conversation history for your reference:\n\n"
            f"{context_summary}\n\n"
            f"[END OF CONTEXT]\n"
            f"Now, please address their current request:"
        )
        
        logger.info(f"[HANDOFF] Built context prefix with {len(context_messages)} messages for {to_domain}")
        return context_prefix

    async def _classify_intent(self, user_message: str, current_domain: str | None) -> Dict[str, Any]:
        """
        Use structured output with Pydantic to classify user intent and detect domain changes.
        
        This uses the beta.chat.completions.parse() API with response_format to ensure
        robust JSON parsing without validation errors.
        
        Args:
            user_message: The user's message to classify
            current_domain: Current active domain (or None for first message)
            
        Returns:
            Dictionary with keys: domain, is_domain_change, confidence, reasoning
        """
        # If no current domain, route to default domain
        if not current_domain:
            return {
                "domain": self._default_domain,
                "is_domain_change": True,
                "confidence": 1.0,
                "reasoning": f"First message, routing to {self._default_domain}"
            }

        # Build classification prompt
        prompt = INTENT_CLASSIFIER_PROMPT.format(
            current_domain=current_domain,
            user_message=user_message
        )

        try:
            # Use OpenAI client directly for structured output support
            from openai import AsyncAzureOpenAI
            
            client = AsyncAzureOpenAI(
                api_key=self.azure_openai_key,
                api_version=self.api_version,
                azure_endpoint=self.azure_openai_endpoint,
            )
            
            # Use beta API with structured output
            completion = await client.beta.chat.completions.parse(
                model=self.azure_deployment,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                response_format=IntentClassification,
            )
            
            # Extract structured result
            intent = completion.choices[0].message.parsed
            
            result = {
                "domain": intent.domain,
                "is_domain_change": intent.is_domain_change,
                "confidence": intent.confidence,
                "reasoning": intent.reasoning,
            }
            
            logger.info(f"[HANDOFF] Intent classification: {result}")
            return result
            
        except Exception as exc:
            logger.error(f"[HANDOFF] Intent classification failed: {exc}", exc_info=True)
            
            # Fallback: randomly select a different domain (not current)
            available_domains = [d for d in DOMAINS.keys() if d != current_domain]
            fallback_domain = random.choice(available_domains) if available_domains else current_domain
            
            logger.warning(f"[HANDOFF] Falling back to random domain: {fallback_domain}")
            
            return {
                "domain": fallback_domain,
                "is_domain_change": fallback_domain != current_domain,
                "confidence": 0.3,
                "reasoning": f"Classification error, randomly selected {fallback_domain}"
            }

    async def chat_async(self, prompt: str) -> str:
        """
        Main chat entry point with intelligent routing and lazy classification.
        
        Flow:
        1. If first message OR lazy classification is disabled: classify intent upfront
        2. If lazy classification enabled: route to current agent first
        3. Check agent response for handoff markers
        4. If handoff detected: run intent classification and re-route
        5. Stream response back to user
        """
        await self._setup_agents()

        # Increment turn counter
        self._current_turn += 1
        self.state_store[self._turn_key] = self._current_turn

        # Determine if we need upfront classification
        is_first_message = self._current_domain is None
        needs_upfront_classification = is_first_message or not self._lazy_classification
        
        target_domain = None
        is_domain_change = False
        
        if needs_upfront_classification:
            # Run intent classification before routing
            logger.info(f"[HANDOFF] Running upfront classification (first_message={is_first_message}, lazy={self._lazy_classification})")
            intent = await self._classify_intent(prompt, self._current_domain)
            target_domain = intent["domain"]
            is_domain_change = intent["is_domain_change"]
            
            # Announce handoff if domain changed
            if is_domain_change and self._current_domain:
                handoff_message = (
                    f"I'll connect you with our {DOMAINS[target_domain]['name']} "
                    f"who can better assist with that."
                )
                
                if self._ws_manager:
                    await self._ws_manager.broadcast(
                        self.session_id,
                        {
                            "type": "handoff_announcement",
                            "from_domain": self._current_domain,
                            "to_domain": target_domain,
                            "message": handoff_message,
                        },
                    )
                
                logger.info(f"[HANDOFF] Domain change: {self._current_domain} -> {target_domain}")
        else:
            # Lazy mode: use current domain (will check response for handoff markers)
            target_domain = self._current_domain
            logger.info(f"[HANDOFF] Using lazy classification, routing to current domain: {target_domain}")

        # Update current domain
        previous_domain = self._current_domain
        self._current_domain = target_domain
        self.state_store[f"{self.session_id}_current_domain"] = target_domain

        # Get the specialist agent and thread
        agent = self._domain_agents[target_domain]
        thread = self._domain_threads[target_domain]
        
        # Prepare the prompt with context if this is a handoff
        actual_prompt = prompt
        if is_domain_change and previous_domain and previous_domain != target_domain:
            context_prefix = await self._build_context_prefix(previous_domain, target_domain)
            if context_prefix:
                actual_prompt = f"{context_prefix}\n\n{prompt}"
                logger.info(f"[HANDOFF] Added context prefix to prompt for {target_domain}")

        # Notify UI that agent started
        if self._ws_manager:
            await self._ws_manager.broadcast(
                self.session_id,
                {
                    "type": "agent_start",
                    "agent_id": target_domain,
                    "agent_name": DOMAINS[target_domain]["name"],
                    "show_message_in_internal_process": is_domain_change,  # Show handoff in left panel
                },
            )

        # Stream response from specialist agent
        full_response = []
        
        try:
            async for chunk in agent.run_stream(actual_prompt, thread=thread):
                # Process contents in the chunk
                if hasattr(chunk, 'contents') and chunk.contents:
                    for content in chunk.contents:
                        # Check for tool/function calls
                        if content.type == "function_call":
                            if self._ws_manager:
                                await self._ws_manager.broadcast(
                                    self.session_id,
                                    {
                                        "type": "tool_called",
                                        "agent_id": target_domain,
                                        "tool_name": content.name,
                                        "turn": self._current_turn,
                                    },
                                )
                
                # Extract text from chunk
                if hasattr(chunk, 'text') and chunk.text:
                    full_response.append(chunk.text)
                    
                    # Broadcast token to WebSocket
                    if self._ws_manager:
                        await self._ws_manager.broadcast(
                            self.session_id,
                            {
                                "type": "agent_token",
                                "agent_id": target_domain,
                                "content": chunk.text,
                            },
                        )
                        
        except Exception as exc:
            logger.error(f"[HANDOFF] Error during agent streaming: {exc}", exc_info=True)
            raise

        assistant_response = ''.join(full_response)

        # Check if lazy classification is enabled and handoff was requested
        if self._lazy_classification and self._detect_handoff_request(assistant_response):
            logger.info(f"[HANDOFF] Handoff marker detected in response, running intent classification")
            
            # Run intent classification to determine new domain
            intent = await self._classify_intent(prompt, target_domain)
            new_target_domain = intent["domain"]
            
            if new_target_domain != target_domain:
                logger.info(f"[HANDOFF] Re-routing from {target_domain} to {new_target_domain}")
                
                # Update domain
                self._current_domain = new_target_domain
                self.state_store[f"{self.session_id}_current_domain"] = new_target_domain
                
                # Announce handoff
                handoff_message = (
                    f"I'll connect you with our {DOMAINS[new_target_domain]['name']} "
                    f"who can better assist with that."
                )
                
                if self._ws_manager:
                    await self._ws_manager.broadcast(
                        self.session_id,
                        {
                            "type": "handoff_announcement",
                            "from_domain": target_domain,
                            "to_domain": new_target_domain,
                            "message": handoff_message,
                        },
                    )
                
                # Get new agent and thread
                new_agent = self._domain_agents[new_target_domain]
                new_thread = self._domain_threads[new_target_domain]
                
                # Build context prefix
                context_prefix = await self._build_context_prefix(target_domain, new_target_domain)
                actual_prompt_handoff = f"{context_prefix}\n\n{prompt}" if context_prefix else prompt
                
                # Notify UI
                if self._ws_manager:
                    await self._ws_manager.broadcast(
                        self.session_id,
                        {
                            "type": "agent_start",
                            "agent_id": new_target_domain,
                            "agent_name": DOMAINS[new_target_domain]["name"],
                            "show_message_in_internal_process": True,
                        },
                    )
                
                # Get response from new agent
                full_response_handoff = []
                try:
                    async for chunk in new_agent.run_stream(actual_prompt_handoff, thread=new_thread):
                        if hasattr(chunk, 'contents') and chunk.contents:
                            for content in chunk.contents:
                                if content.type == "function_call":
                                    if self._ws_manager:
                                        await self._ws_manager.broadcast(
                                            self.session_id,
                                            {
                                                "type": "tool_called",
                                                "agent_id": new_target_domain,
                                                "tool_name": content.name,
                                                "turn": self._current_turn,
                                            },
                                        )
                        
                        if hasattr(chunk, 'text') and chunk.text:
                            full_response_handoff.append(chunk.text)
                            
                            if self._ws_manager:
                                await self._ws_manager.broadcast(
                                    self.session_id,
                                    {
                                        "type": "agent_token",
                                        "agent_id": new_target_domain,
                                        "content": chunk.text,
                                    },
                                )
                except Exception as exc:
                    logger.error(f"[HANDOFF] Error during handoff agent streaming: {exc}", exc_info=True)
                    raise
                
                # Use handoff response
                assistant_response = ''.join(full_response_handoff)
                target_domain = new_target_domain
                thread = new_thread

        # Send final result
        if self._ws_manager:
            await self._ws_manager.broadcast(
                self.session_id,
                {
                    "type": "final_result",
                    "content": assistant_response,
                },
            )

        # Update chat history
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": assistant_response},
        ]
        self.append_to_chat_history(messages)

        # Save thread state for this domain
        thread_state_key = f"{self.session_id}_thread_{target_domain}"
        new_state = await thread.serialize()
        self.state_store[thread_state_key] = new_state

        # Save overall state
        self._setstate({
            "mode": "handoff_multi_domain",
            "current_domain": target_domain,
        })

        return assistant_response
