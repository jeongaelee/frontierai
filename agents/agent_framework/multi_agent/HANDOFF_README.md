# Handoff Multi-Domain Agent - Architecture Guide

## Overview

This is an **optimized handoff pattern** for domain-based multi-agent routing in customer support scenarios. Unlike orchestrator-based approaches (like Magentic), this implementation prioritizes **direct agent-to-user communication** with intelligent routing only when needed.

## ✨ Recent Improvements (v2.0)

### 1. **Structured Output with Pydantic** 🎯
- Intent classification now uses OpenAI's **`beta.chat.completions.parse()`** API
- Pydantic `IntentClassification` model ensures **100% valid JSON** responses
- Eliminates JSON parsing errors that occurred with unstructured LLM outputs
- **Before:** `json.loads()` failures on malformed responses
- **After:** Guaranteed structured output with proper typing

### 2. **Lazy Intent Classification** ⚡
- Classification is now **lazy by default** - only runs when needed!
- **When it runs:**
  - On first message (to route to initial domain)
  - When agent signals handoff via pattern detection
- **When it skips:**
  - During normal conversation within a domain
  - Saves ~1-2 seconds and one LLM call per turn
- **Configuration:** `HANDOFF_LAZY_CLASSIFICATION=true` (default)

### 3. **Pattern-Based Handoff Detection** 🔍
- No LLM needed to detect when agents request handoff!
- Uses regex + keyword proximity to detect phrases like:
  - "This is outside my area. Let me connect you with the right specialist."
  - "outside my domain", "not my expertise", etc.
- **Multiple detection strategies:**
  - Exact phrase matching (highest confidence)
  - Regex patterns for common variations
  - Keyword proximity detection (within 100 chars)
- Fast, reliable, and cost-free

### 4. **Intelligent Error Handling** 🛡️
- If intent classification fails → **random routing** to a different domain
- Prevents getting stuck in broken agent
- Logs all failures for debugging
- Graceful degradation without user impact

### 5. **Configurable Default Domain** 🎛️
- Set starting agent via `HANDOFF_DEFAULT_DOMAIN` environment variable
- Options: `crm_billing`, `product_promotions`, `security_authentication`
- Defaults to `crm_billing` (most common use case)

## Key Design Principles

### 1. **Direct Communication (No Middleman)**
- After initial routing, users communicate **directly** with the assigned specialist agent
- No coordinator agent acting as a middleman for every message
- Specialist agents respond directly to user questions within their domain

### 2. **Lazy Intent Classification**
- Classification is **lazy by default** - only runs when needed
- Uses structured output via `beta.chat.completions.parse()` with Pydantic models
- Runs only on first message or when handoff is detected via pattern matching
- No heavy orchestrator overhead, minimal LLM calls

### 3. **Seamless Handoffs**
- Detects domain changes in real-time
- Announces handoffs to users: "I'll connect you with our Billing Specialist..."
- Preserves conversation context per domain (separate threads)

### 4. **Filtered Tool Access**
- Each specialist has access only to their domain-specific tools
- Prevents tool hallucination and keeps agents focused
- Clear boundaries enforce expertise areas

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User Message                          │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────┐
│              Intent Classifier (Vanilla LLM)                  │
│  "Which domain? Is this a domain change?"                     │
│                                                                │
│  Domains:                                                      │
│  • crm_billing: subscriptions, billing, invoices              │
│  • product_promotions: products, promotions, orders           │
│  • security_authentication: lockouts, security                │
└───────────────────┬───────────────────────────────────────────┘
                    │
                    ├─ No domain change? ──────────────┐
                    │                                   │
                    ├─ Domain change detected? ────┐   │
                    │                               │   │
                    ▼                               ▼   ▼
        ┌──────────────────────┐         ┌────────────────────┐
        │ Announce Handoff      │         │ Continue with      │
        │ "Connecting you       │         │ Current Specialist │
        │  with X Specialist"   │         └────────────────────┘
        └───────────┬───────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────┐
│              Specialist Agent (Direct Communication)            │
│                                                                 │
│  • Maintains own conversation thread                            │
│  • Has domain-specific tools                                    │
│  • Responds directly to user                                    │
│  • Streams tokens via WebSocket                                 │
│                                                                 │
│  If out-of-domain request:                                      │
│  "This is outside my area. Let me connect you with..."          │
│  → Triggers re-classification on next message                   │
└────────────────────────────────────────────────────────────────┘
```

## Domain Specialists

### CRM & Billing Specialist
**Tools:**
- `get_all_customers`, `get_customer_detail`
- `get_subscription_detail`, `get_billing_summary`
- `get_invoice_payments`, `pay_invoice`
- `get_data_usage`, `update_subscription`
- `search_knowledge_base`

**Boundaries:**
- Defers to Product specialist for promotions/plans
- Defers to Security specialist for lockouts/security issues

### Product & Promotions Specialist
**Tools:**
- `get_products`, `get_product_detail`
- `get_promotions`, `get_eligible_promotions`
- `get_customer_orders`
- `search_knowledge_base`

**Boundaries:**
- Defers to Billing specialist for payment/invoice questions
- Defers to Security specialist for lockouts/security issues

### Security & Authentication Specialist
**Tools:**
- `get_security_logs`, `unlock_account`
- `get_support_tickets`, `create_support_ticket`
- `search_knowledge_base`

**Boundaries:**
- Defers to Billing specialist for non-security account issues
- Defers to Product specialist for product/promo questions

## Tool Filtering Architecture 🔒

### How Tool Filtering Works

Each domain specialist has **filtered access** to MCP tools, ensuring agents can only use tools within their domain:

```python
# 1. Connect to MCP server ONCE and load all tools
base_mcp_tool = MCPStreamableHTTPTool(url="http://localhost:8000")
await base_mcp_tool.__aenter__()  # Loads all 20+ tools

# 2. Create filtered wrappers for each domain
crm_tools = FilteredMCPTool(
    mcp_tool=base_mcp_tool,
    allowed_tool_names=["get_customer_detail", "get_billing_summary", ...]
)
crm_tools.filter_functions()  # Only 9 tools accessible

product_tools = FilteredMCPTool(
    mcp_tool=base_mcp_tool,
    allowed_tool_names=["get_products", "get_promotions", ...]
)
product_tools.filter_functions()  # Only 6 tools accessible

# 3. Pass filtered tools to agents
crm_agent = ChatAgent(..., tools=crm_tools)  # Can't access security tools
product_agent = ChatAgent(..., tools=product_tools)  # Can't access billing tools
```

### Benefits

1. **Security**: Agents can't accidentally or maliciously call tools outside their domain
2. **Focus**: Smaller tool list helps LLM select correct tool faster
3. **Clarity**: Reduces hallucination by limiting options
4. **Efficiency**: Single MCP connection shared across all agents

### Implementation Details

**FilteredMCPTool Class:**
- Wraps `MCPStreamableHTTPTool`
- Filters `mcp_tool.functions` list based on `allowed_tool_names`
- Exposes same `.functions` property that `ChatAgent` expects
- Shares underlying MCP connection (efficient)

**DOMAINS Configuration:**
Each domain defines its `"tools"` list:
```python
"crm_billing": {
    "tools": [
        "get_all_customers",
        "get_customer_detail",
        "get_subscription_detail",
        # ... domain-specific tools only
    ]
}
```

## Example Interaction Flows

### Flow 1: Single Domain (Billing Question)

```
User: "What's my current bill?"
  ↓
Intent Classifier: domain=crm_billing, is_domain_change=true
  ↓
Route to: CRM & Billing Specialist
  ↓
Agent: [Uses get_billing_summary tool]
  ↓
Response: "Your current bill is $45.99 for the month..."
```

### Flow 2: Domain Change (Billing → Products)

```
User: "What's my current bill?"
  ↓
CRM & Billing Specialist: "Your current bill is $45.99..."
  ↓
User: "What promotions are available?"
  ↓
Intent Classifier: domain=product_promotions, is_domain_change=true
  ↓
Handoff Announcement: "I'll connect you with our Product & Promotions Specialist..."
  ↓
Product Specialist: [Uses get_promotions tool]
  ↓
Response: "We currently have 3 active promotions..."
```

### Flow 3: Specialist Detects Out-of-Domain

```
User: "What's my current bill?"
  ↓
CRM & Billing Specialist: "Your current bill is $45.99..."
  ↓
User: "Can you unlock my account?"
  ↓
Intent Classifier: domain=crm_billing, is_domain_change=false
  ↓
CRM & Billing Specialist: "This is outside my area. Let me connect you with the right specialist."
  ↓
User: "Yes please"
  ↓
Intent Classifier: domain=security_authentication, is_domain_change=true
  ↓
Security Specialist: [Uses unlock_account tool]
```

## Lazy Classification Flow (v2.0)

### How It Works

**Traditional Flow (v1.0):**
```
User Message → Intent Classification → Route to Agent → Agent Response
     (Every turn runs classification = slow + expensive)
```

**Lazy Flow (v2.0):**
```
User Message → Route to Current Agent → Agent Response → Check for Handoff Marker
                                                                    ↓
                                                    (Only if detected)
                                                                    ↓
                                            Intent Classification → Re-route
```

### Example: Multi-Turn Conversation

```
Turn 1:
User: "What's my bill?"
→ No current domain → Run classification → Route to Billing
Agent: "Your bill is $45.99"

Turn 2:
User: "Can I see the details?"
→ Current domain = Billing → Skip classification → Send to Billing
Agent: "Here are the line items..."
→ Check response → No handoff marker → Done

Turn 3:
User: "What about promotions?"
→ Current domain = Billing → Skip classification → Send to Billing
Agent: "This is outside my area. Let me connect you with the right specialist."
→ Check response → Handoff marker detected! → Run classification → Route to Promotions
Agent: "We have 3 active promotions available..."
```

### Handoff Detection Patterns

The system uses multiple strategies to detect handoff requests:

**1. Exact Template Match (Highest Confidence)**
```regex
"outside my area.*connect you with.*specialist"
```

**2. Domain Boundary Phrases**
```regex
"outside my (domain|expertise|area)"
"not my (specialty|expertise|domain)"
```

**3. Explicit Handoff Language**
```regex
"connect you with.*specialist"
"let me (transfer|route|connect) you"
"better suited to help"
```

**4. Keyword Proximity Detection**
- Keywords from group 1: ["outside", "not my"]
- Keywords from group 2: ["area", "domain", "expertise"]
- Keywords from group 3: ["connect", "transfer", "specialist"]
- Detection: Groups 1 + 2 + 3 within 100 characters

### Configuration

**Enable/Disable Lazy Classification:**
```bash
HANDOFF_LAZY_CLASSIFICATION=true   # Default: enabled
HANDOFF_LAZY_CLASSIFICATION=false  # Runs classification every turn (v1.0 behavior)
```

**Set Default Starting Domain:**
```bash
HANDOFF_DEFAULT_DOMAIN=crm_billing              # Default
HANDOFF_DEFAULT_DOMAIN=product_promotions       # Start with products
HANDOFF_DEFAULT_DOMAIN=security_authentication  # Start with security
```

### Performance Comparison

| Metric | v1.0 (Always Classify) | v2.0 (Lazy) |
|--------|----------------------|-------------|
| LLM calls per turn | 2 (classify + agent) | 1 (agent only)* |
| Latency per turn | ~3-4 seconds | ~1-2 seconds* |
| Handoff detection | LLM-based | Pattern-based (instant) |
| JSON parsing errors | Possible | Eliminated (structured output) |

_*Except when handoff is detected (adds classification call)_

## State Management

### Session State
```python
state_store = {
    # Current active domain
    "{session_id}_current_domain": "crm_billing",
    
    # Turn counter for tool grouping
    "{session_id}_handoff_turn": 5,
    
    # Per-domain conversation threads
    "{session_id}_thread_crm_billing": {...},
    "{session_id}_thread_product_promotions": {...},
    "{session_id}_thread_security_authentication": {...},
}
```

### Thread Isolation
- Each domain specialist maintains its own `AgentThread`
- Threads are serialized and persisted in state store
- When switching domains, the new specialist's thread is restored
- Allows specialists to maintain context within their domain

## WebSocket Events

### Agent Start
```json
{
    "type": "agent_start",
    "agent_id": "crm_billing",
    "agent_name": "CRM & Billing Specialist",
    "show_message_in_internal_process": true  // true if handoff
}
```

### Handoff Announcement
```json
{
    "type": "handoff_announcement",
    "from_domain": "crm_billing",
    "to_domain": "product_promotions",
    "message": "I'll connect you with our Product & Promotions Specialist..."
}
```

### Tool Called
```json
{
    "type": "tool_called",
    "agent_id": "crm_billing",
    "tool_name": "get_billing_summary",
    "turn": 3
}
```

### Agent Token (Streaming)
```json
{
    "type": "agent_token",
    "agent_id": "crm_billing",
    "content": "Your"  // incremental token
}
```

### Final Result
```json
{
    "type": "final_result",
    "content": "Your current bill is $45.99..."
}
```

## Comparison: Handoff vs Magentic Orchestrator

| Feature | Handoff Pattern (This) | Magentic Orchestrator |
|---------|------------------------|----------------------|
| **Communication** | Direct agent-to-user | Via coordinator middleman |
| **Efficiency** | Vanilla LLM for intent | Full orchestrator loop |
| **Routing** | On-demand (when domain changes) | Every message |
| **Context** | Per-domain threads | Single shared context |
| **Tool Access** | Domain-filtered | Defined per participant |
| **Streaming** | Direct from specialist | Via orchestrator events |
| **Best For** | Domain handoffs, support | Complex multi-agent workflows |
| **Cost** | Lower (fewer LLM calls) | Higher (orchestrator overhead) |

## Implementation Details

### Intent Classification
Uses a vanilla LLM call with structured JSON output:
```python
async def _classify_intent(self, user_message: str, current_domain: str) -> Dict:
    prompt = INTENT_CLASSIFIER_PROMPT.format(
        current_domain=current_domain,
        user_message=user_message
    )
    
    messages = [ChatMessage(role=Role.USER, text=prompt)]
    response = await chat_client.get_response(messages, model=self.openai_model_name)
    
    return json.loads(response.messages[0].text)
```

**Returns:**
```json
{
    "domain": "crm_billing",
    "is_domain_change": false,
    "confidence": 0.95,
    "reasoning": "User asking about billing topic"
}
```

### Agent Initialization
All domain specialists are created upfront but remain idle until needed:
```python
for domain_id, domain_config in DOMAINS.items():
    agent = ChatAgent(
        name=domain_id,
        chat_client=chat_client,
        instructions=domain_config["instructions"],
        tools=mcp_tool,
        model=self.openai_model_name,
    )
    
    await agent.__aenter__()
    self._domain_agents[domain_id] = agent
    self._domain_threads[domain_id] = agent.get_new_thread()
```

### Direct Communication
After routing, the specialist agent runs directly with streaming:
```python
agent = self._domain_agents[target_domain]
thread = self._domain_threads[target_domain]

async for chunk in agent.run_stream(prompt, thread=thread):
    # Process and broadcast chunks
    if hasattr(chunk, 'text') and chunk.text:
        await self._ws_manager.broadcast(
            self.session_id,
            {"type": "agent_token", "content": chunk.text}
        )
```

### Context Transfer Between Domains
One of the key features of the handoff pattern is **configurable context transfer** when routing between specialists. This ensures important information (like customer IDs, previous requests) carries over to the new agent.

**Configuration:**
```bash
# Context transfer setting (-1 = all history, 0 = none, N = last N turns)
HANDOFF_CONTEXT_TRANSFER_TURNS=-1  # Default: transfer all history
```

**Options:**

| Value | Behavior | Use Case |
|-------|----------|----------|
| `-1` | Transfer **all** conversation history | Best for full context (default) |
| `0` | **No** context transfer | Each domain starts fresh |
| `1` | Transfer **last 1 turn** (2 messages) | Most recent exchange only |
| `2` | Transfer **last 2 turns** (4 messages) | Recent context window |
| `N` | Transfer **last N turns** | Configurable balance |

**How It Works:**

When a handoff occurs, the new specialist receives the conversation history as a context prefix:

```
[CONTEXT FROM PREVIOUS CONVERSATION]
The user was previously speaking with the CRM & Billing Specialist.
Here is the recent conversation history:

User: My customer ID is 251. What's my bill?
Previous Specialist: Your bill is $150...

[END OF CONTEXT]
Now address their current request:

Am I eligible for promotions?
```

**Example:**

*Without context transfer:*
```
User: "My customer ID is 251. What's my bill?"
CRM: "Your bill is $150..."
User: "Am I eligible for promotions?"
Product: "Could you provide your customer ID?" ❌
```

*With context transfer (default):*
```
User: "My customer ID is 251. What's my bill?"
CRM: "Your bill is $150..."
User: "Am I eligible for promotions?"
Product: [Sees customer ID 251 in context]
Product: "For customer 251, you're eligible for..." ✅
```

**Token Considerations:**

Context is only added once at handoff time, not on every message:

| Setting | Context Size | Approximate Tokens |
|---------|--------------|-------------------|
| `0` | None | 0 |
| `1` | 2 messages | ~100 |
| `2` | 4 messages | ~200 |
| `-1` | All (e.g., 10 msgs) | ~500 |

**Recommendations:**
- **General support:** `-1` (all history) - Best user experience
- **Cost-sensitive:** `2` (last 2 turns) - Balance context with tokens
- **Privacy-sensitive:** `0` (no context) - Domain isolation

## Configuration

### Environment Variables
```bash
# Azure OpenAI (for agents and intent classifier)
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# MCP Server (for tools)
MCP_SERVER_URI=http://localhost:8000

# Context Transfer Configuration
HANDOFF_CONTEXT_TRANSFER_TURNS=-1  # -1=all, 0=none, N=last N turns

# Lazy Classification Configuration (NEW!)
HANDOFF_LAZY_CLASSIFICATION=true      # Enable lazy classification (default: true)
HANDOFF_DEFAULT_DOMAIN=crm_billing    # Default starting domain (default: crm_billing)
                                       # Options: crm_billing, product_promotions, security_authentication

# Agent Module
AGENT_MODULE=agents.agent_framework.multi_agent.handoff_multi_domain_agent
```

### Frontend
Use the React frontend for best streaming visualization:
```bash
cd agentic_ai/applications/react-frontend
npm install
npm start
```

## Troubleshooting

### Issue: Agent doesn't detect domain changes
**Cause:** Intent classifier returning low confidence or defaulting to current domain

**Solution:**
- Check intent classifier logs for reasoning
- User should be more explicit: "I need help with [domain]"
- Adjust `INTENT_CLASSIFIER_PROMPT` for better detection

### Issue: Tools not available to agent
**Cause:** MCP server not running or tool filtering issue

**Solution:**
- Verify `MCP_SERVER_URI` is correct and server is running
- Check logs for MCP tool initialization messages
- Ensure domain's tool list matches actual MCP tool names

### Issue: Context lost after handoff
**Cause:** Thread state not properly persisted

**Solution:**
- Check that `state_store` is properly configured
- Verify thread serialization/deserialization is working
- Each domain maintains separate thread - context doesn't carry over between domains by design

### Issue: Repeated handoff loops
**Cause:** Specialist agent not handling request properly

**Solution:**
- Review specialist instructions for clarity
- Ensure tools are working correctly
- Check if user is asking genuinely out-of-domain questions

## Future Enhancements

1. **Smart Context Transfer**: Pass relevant context when handing off between domains
2. **Confidence Thresholds**: Only route if classifier confidence > X%
3. **Fallback Agent**: General assistant for ambiguous requests
4. **Multi-Domain Queries**: Handle requests spanning multiple domains in single response
5. **Agent Suggestions**: "I can help with billing, but you might also want to ask about promotions..."

## Key Advantages

1. ✅ **Efficient**: No orchestrator overhead for every message
2. ✅ **Natural**: Direct agent-to-user conversation feels more human
3. ✅ **Scalable**: Easy to add new domain specialists
4. ✅ **Maintainable**: Clean separation of concerns
5. ✅ **Observable**: Full streaming visibility via WebSocket
6. ✅ **Cost-effective**: Fewer LLM calls than orchestrator patterns

## When to Use This Pattern

**Use handoff pattern when:**
- User conversations naturally stay within a domain
- Clear domain boundaries exist
- Want to minimize LLM calls and cost
- Direct agent communication is preferred

**Use orchestrator pattern (Magentic) when:**
- Complex multi-agent collaboration needed
- Tasks require multiple specialists simultaneously
- Need centralized decision-making and coordination
- Cost is less of a concern
