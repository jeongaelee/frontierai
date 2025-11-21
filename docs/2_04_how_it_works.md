# Part 2: Microsoft AI Agentic Workshop

## Step 4: Microsoft AI Agentic 워크샵 작동 원리
  
이 문서는 Microsoft AI Agentic Workshop의 아키텍처와 워크플로우를 설명하며, 구성 요소 간의 상호작용, 사용 가능한 API 엔드포인트, 배포 및 실험을 위한 모범 사례를 포함합니다.  

## 사전 준비 사항
- MCP server, backend, frontend가 모두 실행 중이어야 합니다.  
- AI 에이전트 및 다중 에이전트 시스템에 대한 기본 이해  

## 아키텍처 개요
  
### 1. 구성 요소 흐름  
  
워크샵은 다음 실행 흐름을 따릅니다:  
  
1. **Web UI (React 또는 Streamlit):** 사용자가 메시지를 입력하고 어시스턴트와 상호작용합니다. 각 채팅 세션에 대해 고유한 세션 ID가 생성됩니다.  
  
2. **Backend (FastAPI):** WebSocket 또는 REST API를 통해 사용자 프롬프트를 수신하고, 세션 및 채팅 기록을 관리하며, 환경 설정에 따라 에이전트를 검색하거나 생성합니다.  
  
3. **Agent (specified by AGENT_MODULE):** Azure OpenAI와 선택적 MCP 도구를 사용하여 입력을 처리합니다. 에이전트는 구성에 따라 단일, 다중 에이전트 또는 협업 모드로 작동할 수 있습니다.  
  
4. **Chat History:** 대화 기록은 세션별로 저장되며, 프론트엔드에 표시하거나 필요에 따라 재설정할 수 있습니다.  
  
5. **WebSocket Streaming (React only):** 실시간 이벤트는 에이전트의 사고, 도구 호출, 오케스트레이터 계획 및 스트리밍 토큰을 React UI에 방송합니다.  

### 2. 에이전트 유형 및 스트리밍  
  
 다양한 에이전트 유형은 서로 다른 스트리밍 기능을 제공합니다:  
  
- **Agent Framework agents:** 스트림 이벤트를 WebSocket 콜백을 통해 실시간 UI 업데이트로 전송합니다.  
- **Other agents (Autogen, Semantic Kernel):** REST API를 통해 완전한 응답을 반환합니다.  
  
## API 엔드포인트  
  
### FastAPI Backend Endpoints  
  
The backend provides these API endpoints for integration:  
  
- **`POST /chat`:** JSON payload로 `{ "session_id": ..., "prompt": ... }`를 전송합니다. 어시스턴트의 응답을 반환합니다.  
  
- **`POST /reset_session`:** `{ "session_id": ... }` 페이로드를 전송하여 해당 세션의 대화 기록을 지웁니다.  
  
- **`GET /history/{session_id}`:** 주어진 세션에 대한 모든 이전 메시지를 가져옵니다.  
  
## 설정 및 Best Practices  
  
### 환경 설정

주요 설정 고려 사항:
- 현재의 세션 저장소는 메모리 내 Python 딕셔너리를 사용합니다. 프로덕션 배포의 경우 Redis 또는 데이터베이스와 같은 영구 저장소로 대체하십시오.  
- `.env` 파일에 있는 비밀 정보(예: API 키)가 버전 관리에 절대 커밋되지 않도록 하십시오.  
-  MCP 서버와 Azure 엔드포인트 URL은 백엔드에서 접근 가능해야 합니다.  
- 다양한 에이전트 동작을 실험하려면 `.env`에서 `AGENT_MODULE`을 조정하십시오.  
  
### Production 고려 사항  
  
Production 환경에서는 다음을 고려하십시오:  
  
- in-memory 세션 스토리지를 persistent storage (Redis, CosmosDB 등)로 교체하십시오.  
- 적절한 인증 및 권한 부여를 구현하십시오. (Authentication & Authorization)
- Secret 관리를 위하여 Azure Key Vault를 사용하십시오.  
- 모니터링과 로깅을 설정하십시오. (Monitoring & Logging)  
- 고가용성을 위한 로드 밸런싱을 구성하십시오.  
  
## 성공 기준  
- 애플리케이션 아키텍처에 대한 완전한 이해  
- 사용 가능한 API 엔드포인트에 대한 지식  
- 구성 옵션 및 모범 사례에 대한 이해
- 에이전트 동작 및 배포 설정을 사용자 지정하는 능력  
  
## Credits and Acknowledgments  
  
**Technologies Used:**  
- **[Microsoft Agent Framework](https://github.com/microsoft/agent-framework)** - Microsoft's latest agentic AI framework  
- **Microsoft Azure OpenAI Service**  
- **MCP Project** - Model Context Protocol  
- **AutoGen** - Multi-agent conversation framework  
- **Semantic Kernel** - Microsoft's AI orchestration SDK  
  
**Team Acknowledgments:**  
- Microsoft Agent Framework Team  
- Microsoft Azure OpenAI Service Team  
- MCP Project Contributors  
- AutoGen Community  
- SDP CSA & SE Team - James Nguyen, Anil Dwarkanath, Nicole Serafino, Claire Rehfuss, Patrick O'Malley, Kirby Repko, Heena Ugale, Aditya Agrawal  
  
**다음 단계**:  다양한 에이전트 구성을 실험하려면 `.env` 파일에서 `AGENT_MODULE`을 수정하거나, 자세한 [Agent Framework 문서](../agentic_ai/agents/agent_framework/README.md)를 탐색하십시오.
