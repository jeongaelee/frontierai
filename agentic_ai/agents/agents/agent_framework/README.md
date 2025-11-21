# Microsoft Agent Framework Patterns - Implementation Guide

This directory contains production-ready implementations of multi-agent patterns using [Microsoft Agent Framework](https://github.com/microsoft/agent-framework). These patterns demonstrate different approaches to building intelligent, collaborative AI systems.

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Available Patterns](#available-patterns)
- [Architecture Overview](#architecture-overview)
- [Documentation](#documentation)
- [Configuration](#configuration)
- [Choosing the Right Pattern](#choosing-the-right-pattern)

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+** with dependencies installed via `uv sync` or `pip install -r requirements.txt`
2. **Node.js 16+** (for React frontend) - Check with `node --version`
3. **Running MCP Server** on `http://localhost:8000`
4. **Azure OpenAI** endpoint and API key configured in `.env`

### Setup Steps

**1. Install Python dependencies:**

*With uv (recommended):*
```bash
cd agentic_ai/applications
uv sync
```

*Or with pip:*
```bash
cd agentic_ai/applications
pip install -r requirements.txt
```

**2. Install Node.js (if needed):**

The React frontend requires Node.js 16+ and npm:

- **Windows/macOS/Linux:** Download from [https://nodejs.org/](https://nodejs.org/) (LTS version)
- **Windows (winget):** `winget install OpenJS.NodeJS.LTS`
- **macOS (Homebrew):** `brew install node`

Verify installation:
```bash
node --version  # Should be v16+
npm --version   # Should be v8+
```

**3. Configure your agent:**

Edit `agentic_ai/applications/.env`:
```bash
# Choose your pattern
AGENT_MODULE=agents.agent_framework.single_agent
# OR
AGENT_MODULE=agents.agent_framework.multi_agent.magentic_group
# OR
AGENT_MODULE=agents.agent_framework.multi_agent.handoff_multi_domain_agent

# Configure Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4.1
AZURE_OPENAI_API_VERSION=2025-03-01-preview

# MCP Server
MCP_SERVER_URI=http://localhost:8000/mcp
```

**4. Start the MCP Server:**

*Terminal 1:*
```bash
cd mcp
uv run python mcp_service.py
# Server runs on http://localhost:8000
```

**5. Start the Backend:**

*Terminal 2:*
```bash
cd agentic_ai/applications
uv run python backend.py
# Backend runs on http://localhost:7000
```

**6. Start the React Frontend:**

*Terminal 3:*
```bash
cd agentic_ai/applications/react-frontend

# First time only: Install dependencies
npm install

# Start development server
npm start

# App opens at http://localhost:3000
```

📚 **[See detailed React UI features and configuration →](../../applications/react-frontend/README.md)**

**Optional: Configure React backend URL**

Create `react-frontend/.env` if you need to change the backend URL:
```bash
REACT_APP_BACKEND_URL=http://localhost:7000
```

**Troubleshooting:**
- **Port 3000 in use?** React will prompt you to use a different port. Type `Y`.
- **WebSocket errors?** Ensure backend is running on port 7000.
- **npm install fails?** Try: `npm cache clean --force` and retry.

### Quick Test

Once all three terminals are running:

1. Open http://localhost:3000 in your browser
2. Type: "Customer 251, what's my billing summary?"
3. Watch the left panel to see:
   - Intent classification (Handoff pattern)
   - Orchestrator planning (Magentic pattern)
   - Agent tool calls in real-time
   - Final response in the chat area

### Alternative: Streamlit Frontend

If you prefer a simpler UI without the React setup:

```bash
cd agentic_ai/applications
uv run streamlit run frontend.py
# Opens at http://localhost:8501
```

**Trade-offs:**
- ✅ **Streamlit:** Simpler setup, no Node.js required
- ✅ **React:** Real-time streaming, internal process visibility, tool call tracking ([See UI features →](../../applications/react-frontend/README.md))

**Recommendation:** Use React for Agent Framework patterns to see the full orchestration and agent thinking process.



## 🎯 Available Patterns

### 1. Single Agent (`single_agent.py`)

**Best for:** Simple conversational AI, Q&A systems, single-domain tasks

A straightforward agent that uses MCP tools to answer questions and perform tasks within a single domain.

**Features:**
- ✅ Simple setup and operation
- ✅ MCP tool integration
- ✅ Streaming support
- ✅ Session persistence

**Configuration:**
```bash
AGENT_MODULE=agents.agent_framework.single_agent
```

**Use When:**
- Single domain/topic
- Direct user-agent conversation
- Minimal complexity needed

---

### 2. Magentic Orchestration (`multi_agent/magentic_group.py`)

**Best for:** Complex multi-agent collaboration, research tasks, multi-step workflows

An orchestrator-based pattern where a manager coordinates multiple specialist agents working together on complex tasks.

**Features:**
- ✅ Automatic planning and coordination
- ✅ Progress tracking and replanning
- ✅ Multiple agents collaborating simultaneously
- ✅ Checkpoint-based resume capability
- ✅ Full streaming visibility

**Configuration:**
```bash
AGENT_MODULE=agents.agent_framework.multi_agent.magentic_group
MAGENTIC_LOG_WORKFLOW_EVENTS=true
MAGENTIC_ENABLE_PLAN_REVIEW=true
MAGENTIC_MAX_ROUNDS=10
```

**Architecture:**
```
User Request
    ↓
Manager (Planner)
    ↓
┌─────────────────────────────────┐
│  Coordinates Multiple Agents:   │
│  • Billing Specialist           │
│  • Product Specialist           │
│  • Security Specialist          │
└─────────────────────────────────┘
    ↓
Manager synthesizes final answer
    ↓
Response to User
```

**Use When:**
- Complex tasks requiring multiple specialists
- Need centralized planning/coordination
- Tasks can be parallelized
- Budget allows for orchestrator overhead

📚 **[Full Documentation](multi_agent/MAGENTIC_README.md)**

---

### 3. Handoff Pattern (`multi_agent/handoff_multi_domain_agent.py`)

**Best for:** Customer support, domain-specific routing, efficient multi-domain conversations

A lightweight pattern where users communicate **directly** with domain specialists. The system intelligently routes between specialists only when needed.

**Features:**
- ✅ Direct agent-to-user communication (no middleman)
- ✅ Intelligent intent classification
- ✅ Per-domain conversation threads
- ✅ Configurable context transfer
- ✅ Domain-specific tool filtering
- ✅ Cost-efficient (fewer LLM calls)

**Configuration:**
```bash
AGENT_MODULE=agents.agent_framework.multi_agent.handoff_multi_domain_agent

# Context transfer: -1=all, 0=none, N=last N turns
HANDOFF_CONTEXT_TRANSFER_TURNS=-1
```

**Architecture:**
```
User Message
    ↓
Intent Classifier (lightweight LLM call)
    ↓
Route to appropriate specialist
    ↓
Specialist Agent (direct communication)
    ↓
Direct response to user

[On domain change detected]
    ↓
Transfer context to new specialist
    ↓
Continue conversation with new agent
```

**Key Advantages:**
- **Efficient:** 33% fewer LLM calls vs orchestrator
- **Natural:** Direct conversation with specialists
- **Smart Context:** Configurable history transfer on handoff
- **Scalable:** Easy to add new domain specialists

**Use When:**
- User conversations stay within a domain
- Clear domain boundaries exist
- Want to minimize LLM calls and cost
- Direct agent communication is preferred
- Customer support scenarios

📚 **[Full Documentation](multi_agent/HANDOFF_README.md)**

---

## 🏗️ Architecture Overview

### State Management

All patterns use a consistent state management approach:

- **Session-based storage:** Each user session has isolated state
- **Thread persistence:** Conversation history saved per agent/domain
- **Checkpoint support:** Resume interrupted workflows
- **Pluggable backends:** Redis, Cosmos DB, or in-memory

📚 **[State Management Guide](STATE_MANAGEMENT.md)**

### Common Components

```
agentic_ai/agents/agent_framework/
├── base_agent.py                    # Base class for all agents
├── single_agent.py                  # Single agent implementation
├── STATE_MANAGEMENT.md              # State persistence guide
└── multi_agent/
    ├── magentic_group.py            # Magentic orchestrator
    ├── handoff_multi_domain_agent.py # Handoff pattern
    ├── MAGENTIC_README.md           # Magentic documentation
    └── HANDOFF_README.md            # Handoff documentation
```

---

## ⚙️ Configuration

### Environment Variables

**Required for all patterns:**

```bash
# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# MCP Server (for tools)
MCP_SERVER_URI=http://localhost:8000
```

**Pattern-specific:**

```bash
# Magentic Orchestration
MAGENTIC_LOG_WORKFLOW_EVENTS=true        # Enable event logging
MAGENTIC_ENABLE_PLAN_REVIEW=true         # Enable plan review
MAGENTIC_MAX_ROUNDS=10                    # Max coordination rounds

# Handoff Pattern
HANDOFF_CONTEXT_TRANSFER_TURNS=-1        # -1=all, 0=none, N=last N turns
```

### Selecting a Pattern

Set `AGENT_MODULE` in `.env`:

```bash
# Single agent
AGENT_MODULE=agents.agent_framework.single_agent

# Magentic orchestration
AGENT_MODULE=agents.agent_framework.multi_agent.magentic_group

# Handoff pattern
AGENT_MODULE=agents.agent_framework.multi_agent.handoff_multi_domain_agent
```

---

## 🤔 Choosing the Right Pattern

### Decision Matrix

| Requirement | Single Agent | Magentic | Handoff |
|-------------|--------------|----------|---------|
| **Simple Q&A** | ✅ Best | ❌ Overkill | ❌ Overkill |
| **Multiple domains** | ❌ No | ✅ Yes | ✅ Yes |
| **Complex coordination** | ❌ No | ✅ Best | ⚠️ Limited |
| **Cost-sensitive** | ✅ Lowest | ❌ Highest | ✅ Medium |
| **User experience** | ✅ Fast | ⚠️ Slower | ✅ Fast |
| **Context continuity** | ✅ Yes | ✅ Yes | ✅ Configurable |
| **Parallel execution** | ❌ No | ✅ Yes | ❌ No |
| **Customer support** | ⚠️ Limited | ⚠️ Slow | ✅ Best |

### Use Case Recommendations

#### Customer Support / Service Desk
**👉 Handoff Pattern**
- Direct specialist communication
- Smart context transfer
- Cost-efficient
- Fast response times

#### Research / Analysis Tasks
**👉 Magentic Orchestration**
- Multiple specialists collaborate
- Complex multi-step workflows
- Automatic planning and coordination
- Parallel task execution

#### Simple Chatbot / FAQ
**👉 Single Agent**
- Straightforward Q&A
- Single domain
- Minimal setup
- Lowest cost

#### E-commerce Assistant
**👉 Handoff Pattern**
- Product browsing → Checkout → Support
- Clear domain boundaries
- Context carries customer info
- Efficient routing

#### Complex Problem Solving
**👉 Magentic Orchestration**
- Multiple data sources
- Interdependent tasks
- Need planning and replanning
- Budget for orchestrator overhead

---

## 📊 Performance Comparison

### Token Usage (5-turn conversation)

| Pattern | LLM Calls | Approx. Tokens | Relative Cost |
|---------|-----------|----------------|---------------|
| **Single Agent** | 5 | ~2,500 | 1.0x (baseline) |
| **Handoff** | 10 | ~5,000 | 2.0x |
| **Magentic** | 15 | ~12,000 | 4.8x |

*Note: Assumes same domain (no handoffs for Handoff pattern)*

### Latency

| Pattern | First Response | Avg. Response | Relative Speed |
|---------|---------------|---------------|----------------|
| **Single Agent** | ~1s | ~1s | 1.0x (fastest) |
| **Handoff** | ~1.5s | ~1.2s | 1.2x |
| **Magentic** | ~3s | ~2.5s | 2.5x |

*Note: Includes intent classification, planning, and coordination overhead*

---

## 🔧 Development

### Project Structure

```
agentic_ai/
├── agents/
│   ├── base_agent.py              # Base agent class
│   └── agent_framework/
│       ├── single_agent.py        # Single agent
│       ├── STATE_MANAGEMENT.md    # State guide
│       ├── README.md              # This file
│       └── multi_agent/
│           ├── magentic_group.py
│           ├── handoff_multi_domain_agent.py
│           ├── MAGENTIC_README.md
│           └── HANDOFF_README.md
├── applications/
│   ├── backend.py                 # FastAPI + WebSocket
│   ├── frontend.py                # Streamlit UI
│   ├── react-frontend/            # React UI (recommended)
│   └── .env                       # Configuration
└── scenarios/                     # Additional examples
```

### Testing

```bash
# Start MCP server
cd mcp
uv run python mcp_service.py

# Start backend
cd agentic_ai/applications
uv run python backend.py

# Start React frontend
cd react-frontend
npm start
```

📚 **[React Frontend Documentation →](../../applications/react-frontend/README.md)**

### Adding a New Pattern

1. Create agent class inheriting from `BaseAgent`
2. Implement `async def chat_async(self, prompt: str) -> str`
3. Add `set_websocket_manager()` for streaming support
4. Use `self.state_store` for persistence
5. Document in pattern-specific README.md

---

## 📚 Documentation

### Core Guides

- **[State Management Guide](STATE_MANAGEMENT.md)** - Persistence, threads, checkpoints
- **[Magentic Orchestration](multi_agent/MAGENTIC_README.md)** - Multi-agent coordination
- **[Handoff Pattern](multi_agent/HANDOFF_README.md)** - Domain routing and context transfer

### External Resources

- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [Agent Framework Python Docs](https://github.com/microsoft/agent-framework/tree/main/python)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

---

## 🎓 Examples

### Single Agent Chat

```python
from agents.agent_framework.single_agent import Agent

state_store = {}
agent = Agent(state_store, session_id="user123")

response = await agent.chat_async("What's the weather today?")
print(response)
```

### Magentic Coordination

```python
from agents.agent_framework.multi_agent.magentic_group import Agent

state_store = {}
agent = Agent(state_store, session_id="user123")

# Complex task requiring multiple specialists
response = await agent.chat_async(
    "Analyze customer 251's billing, check eligible promotions, "
    "and verify account security status"
)
print(response)
```

### Handoff Routing

```python
from agents.agent_framework.multi_agent.handoff_multi_domain_agent import Agent

state_store = {}
agent = Agent(state_store, session_id="user123")

# First message routes to billing
response = await agent.chat_async("Customer 251, what's my bill?")

# Second message detects domain change and routes to products
response = await agent.chat_async("Am I eligible for promotions?")
# Context automatically transferred - knows customer ID is 251
print(response)
```

---

## 🤝 Contributing

When implementing new patterns:

1. **Extend BaseAgent** for consistent interface
2. **Use state_store** for persistence
3. **Support streaming** via WebSocket manager
4. **Document thoroughly** with pattern-specific README
5. **Add configuration** examples to this guide

---

## 📝 License

This code is part of the OpenAI Workshop and follows the repository's license terms.

---

## 🆘 Support

For questions and issues:

1. Check pattern-specific documentation
2. Review [State Management Guide](STATE_MANAGEMENT.md)
3. See [Microsoft Agent Framework docs](https://github.com/microsoft/agent-framework)
4. Open an issue in the repository

---

## ✨ Key Takeaways

- **Single Agent**: Simple, fast, single-domain
- **Magentic**: Complex coordination, multiple agents, powerful planning
- **Handoff**: Efficient routing, direct communication, smart context transfer

Choose the pattern that matches your use case, not the one that sounds most impressive! 🚀
