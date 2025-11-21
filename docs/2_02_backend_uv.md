# Part 2: Microsoft AI Agentic Workshop

## Step 3: Application Backend Server

이 단계에서는 uv를 사용하여 Microsoft AI Agentic Workshop을 위한 백엔드 서비스를 구성하고 실행합니다. 백엔드는 고급 멀티 에이전트 기능을 갖춘 Microsoft의 Agent Framework를 완벽하게 지원합니다.

## 사전 준비 사항
- [Step 1: Workshop Setup](2_00_setup.md) 완료
- [Step 2: MCP Setup (uv)](01_mcp_uv.md) 완료
- MCP 구동 확인: `http://localhost:8000/mcp`
- uv 설치 완료

## Microsoft Agent Framework 옵션

**Single Agent (`agents.agent_framework.single_agent`):**

- MCP 도구를 사용하는 기본 ChatAgent
- WebSocket을 통한 토큰 단위 스트리밍
- React UI에서 도구 호출 가시화
- 요청 간 세션 상태 지속(persistence)

**Magentic Multi-Agent (`agents.agent_framework.multi_agent.magentic_group`):**
- 지능적인 오케스트레이터가 전문 에이전트(CRM/청구, 제품/프로모션, 보안)를 조율
- 오케스트레이터 계획 및 에이전트 응답의 실시간 스트리밍
- Human-in-the-loop 지원을 위한 맞춤형 진행 레저(progress ledger를 제공)  
- 재개 가능한 워크플로우를 위한 체크포인팅 기능 기원
- React UI는 전체 내부 프로세스 표시: 작업 레저, 지시사항, 에이전트 도구 호출

**Handoff Multi-Agent (`agents.agent_framework.multi_agent.handoff_multi_domain_agent`):**
- 지능형 도메인 라우팅을 통한 에이전트-사용자 직접 통신
- 전문가 간 컨텍스트 전송 설정 가능 (고객 정보와 히스토리 유지)
- 원활한 핸드오프를 위한 스마트 인텐트 분류
- 비용 효율적 (오케스트레이터 패턴 대비 LLM 호출 33% 감소)

### 1. Agent Framework 설정

> **Action Items:**
> `agentic_ai/applications` 폴더 내에 있는 `.env` 파일에서 다음 줄 중 하나의 주석 처리를 해제하세요:
> ```bash
> # In your .env file in agentic_ai/applications folder, uncomment one of following for agent framework:
> AGENT_MODULE="agents.agent_framework.single_agent"
> # OR
> AGENT_MODULE="agents.agent_framework.multi_agent.magentic_group"
> # OR
> AGENT_MODULE="agents.agent_framework.multi_agent.handoff_multi_domain_agent"
> ```
> 
> Add additional environment variables to the bottom of your existing `.env` file:
> 
> **For Magentic Orchestration Settings (magentic_group):**
> ```bash
> MAGENTIC_LOG_WORKFLOW_EVENTS=true
> MAGENTIC_ENABLE_PLAN_REVIEW=false  # Set to true for human-in-the-loop plan approval
> MAGENTIC_MAX_ROUNDS=10
> ```
> 
> **For Handoff Agent Context Transfer (handoff_multi_domain_agent):**
> ```bash
> HANDOFF_CONTEXT_TRANSFER_TURNS=-1  # -1=all history, 0=none, N=last N turns
> ```
  
📚 **[자세한 패턴 가이드 확인 및 설정 →](../agentic_ai/agents/agent_framework/README.md)**

### 2. Backend 서비스 실행

> **Action Items:**
> 터미널 창을 새로 열고 MCP 서버가 실행 중인 창과는 별도로 진행하세요.
> ![new terminal](media/01_mcp_new_terminal.png)
> Navigate to the applications directory and start the backend:
> ```bash
> cd agentic_ai/applications
> uv run python backend.py
> ```

### 3. 프론트엔드 경험 선택

## 📊 Frontend 비교

| Feature | React Frontend | Streamlit Frontend |
|---------|---------------|-------------------|
| **Real-time streaming** | ✅ Token-by-token | ❌ Full response only |
| **Internal process visibility** | ✅ Orchestrator, agents, tools | ❌ Final answer only |
| **Tool call tracking** | ✅ Per-turn history | ❌ Not shown |
| **Multi-agent visualization** | ✅ Agent timeline & planning | ❌ Not shown |
| **Best for Agent Framework** | ✅ **Recommended** | ⚠️ Basic support |
| **Setup complexity** | Medium (npm install) | Low (no additional setup) |
| **Best use case** | Development, demos, debugging | Quick testing, simple chat |

**권장:**
- React를 사용: Agent Framework 에이전트의 전체 다중 에이전트 오케스트레이션을 확인하세요.
- Streamlit을 사용: 모든 에이전트 유형의 빠른 테스트 또는 간단한 데모를 진행하세요.
- 본 실습에서는 React 프론트엔드를 사용합니다.

## 성공 기준
- Backend 서비스가 `http://localhost:7000`에서 실행 중이어야 합니다.
- Agent Framework이 적절히 구성되어야 합니다.
- Backend가 MCP 서버와 통신할 수 있어야 합니다.
  - 온라인 상태를 확인하는 샘플 curl 명령어: `curl -X 'POST' 'http://localhost:7000/chat'  -H 'accept: application/json'  -H 'Content-Type: application/json'  -d '{"session_id": "123", "prompt": "What can you help me with?"}'`
- 프론트엔드와 연결할 준비가 되어 있어야 합니다.

## 다음 단계: Frontend 서비스

* [Hands-on Lab 3 – Frontend](2_03_frontend_react.md)

## 실습 순서

### Part 1
* [Microsoft Agent Framework Basic Concept HoL](00_basic_concept.md)

### Part 2
* [Hands-on Lab 0 – Setup](2_00_setup.md)
* [Hands-on Lab 1 – MCP Server](2_01_mcp_uv.md)
* [Hands-on Lab 2 – Backend](2_02_backend_uv.md)
* [Hands-on Lab 3 – Frontend](2_03_frontend_react.md)


**📌 Important:** Agent Framework은 **React 프론트엔드**와 함께 사용할 때 내부 에이전트 프로세스, 오케스트레이터 계획 및 도구 호출을 실시간으로 시각화하는 데 가장 적합합니다.