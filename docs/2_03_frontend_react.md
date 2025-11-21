# Part 2: Microsoft AI Agentic Workshop

## Step 4: Frontend Setup with React

이 단계에서는 Microsoft AI Agentic Workshop을 위한 React 프론트엔드를 설정하고 실행합니다. React 프론트엔드는 실시간 토큰 단위 스트리밍과 내부 에이전트 프로세스 가시성을 제공하는 Microsoft Agent Framework 에이전트에 이상적인 고급 스트리밍 시각화를 제공합니다.

## 사전 준비 사항
- [Step 1: Workshop Setup](2_00_setup.md) 완료
- [Step 2: MCP Setup (uv)](01_mcp_uv.md) 완료
- [Step 3: Backend Setup (uv)](02_backend_uv.md) 완료
- MCP 구동 확인: `http://localhost:8000/mcp`
- Backend 서비스 구동 확인: `http://localhost:7000/chat`

### 1. Node.js 설치

React Frontend를 실행하려면 Node.js 16 이상과 npm이 필요합니다.

> **Action Items:**
> 새로운 터미널 창을 열고 MCP 서버 및 백엔드를 실행 중인 창과는 별도로 진행하세요.
> ![new terminal](media/01_mcp_new_terminal.png)
> Node.js와 npm이 설치되어 있는지 확인하세요:
> ```bash
> node --version  # Should be v16 or higher
> npm --version   # Should be v8 or higher
> ```
> 
> 설치되어 있지 않은 경우, 다음 설치 방법 중 하나를 선택하세요:
> - **Windows/macOS/Linux:** [https://nodejs.org/](https://nodejs.org/)에서 LTS 버전을 다운로드하여 설치하세요.
> - **Windows (대안):** `winget install OpenJS.NodeJS.LTS` 명령어를 사용하세요.
> - **macOS (대안):** `brew install node` 명령어를 사용하세요.

### 2. Frontend 설정 (optional)

React frontend는 기본적으로 `http://localhost:7000`에 연결됩니다.

> **Action Items (Optional):**
> Backend URL을 사용자 지정하려면 `react-frontend` 디렉터리에 `.env` 파일을 만드세요:
> ```bash
> # react-frontend/.env
> REACT_APP_BACKEND_URL=http://localhost:7000
> ```

### 3. 의존성 설치 및 React 프론트엔드 시작

> **Action Items:**
> `agentic_ai/applications`에서 React 프론트엔드 디렉터리로 이동하세요:
> ```bash
> cd react-frontend
> ```
> 
> Dependencies 설치 (처음 실행 시 또는 package.json 변경 후):
> ```bash
> npm install
> ```
> 
> React 개발 서버 시작:
> ```bash
> npm start
> ```
> 
> React 앱이 자동으로 `http://localhost:3000`에서 열립니다. 자동으로 열리지 않으면 브라우저에서 `http://localhost:3000`으로 이동하세요.

## 성공 기준
- React frontend가 `http://localhost:3000`에서 실행 중이어야 합니다.
- Frontend가 성공적으로 Backend에 `http://localhost:7000`으로 연결되어야 합니다.
- Chat 인터페이스로 AI 에이전트와 상호작용할 수 있어야 합니다.
- 실시간 스트리밍 및 에이전트 프로세스 visibility가 작동해야 합니다.

## 트러블슈팅
- **포트 3000이 이미 사용 중인가요?** React 앱이 다른 포트를 사용하겠냐고 묻습니다. `Y`를 입력하여 수락하세요.
- **npm install이 실패하나요?** npm 캐시를 지우고 다시 시도해 보세요: `npm cache clean --force`
- **WebSocket 연결 오류가 발생하나요?** 백엔드가 포트 7000에서 실행 중인지, 방화벽이 연결을 차단하지 않는지 확인하세요.

**축하합니다**: 모든 단계를 성공적으로 완료했다면, 설정이 완료되었으며 에이전트가 실행 중이어야 합니다! 자세한 내용은 [작동 원리 →](2_04_how_it_works.md)에서 확인하세요.

## 실습 순서

### Part 1
* [Microsoft Agent Framework Basic Concept HoL](00_basic_concept.md)

### Part 2
* [Hands-on Lab 0 – Setup](2_00_setup.md)
* [Hands-on Lab 1 – MCP Server](2_01_mcp_uv.md)
* [Hands-on Lab 2 – Backend](2_02_backend_uv.md)
* [Hands-on Lab 3 – Frontend](2_03_frontend_react.md)