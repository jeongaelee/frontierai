# Part 2: Microsoft AI Agentic Workshop

> Note: 워크샵 시나리오 개요는 설정을 시작하기 전에 [여기](../SCENARIO.md)에서 읽어보세요.

## Step 2: MCP Server
이 단계에서는 Microsoft AI Agentic를 활용한 애플리케이션을 위한 MCP (Model Control Protocol)를 설정합니다. 이를 위해 필요한 Python 종속 항목을 설치하고 MCP 서버를 실행합니다.

## 사전준비사항
- [Step 1: Workshop Setup](2_00_setup.md) 완료

### 1. uv 설치

- ⚡`uv`로 빠른 설정

- [**uv**](https://github.com/astral-sh/uv)는 Rust로 작성된 초고속 Python 패키지 설치 및 해결 도구입니다. `pip`보다 10-100배 빠르며 가상 환경을 자동으로 관리합니다.

    > **Action Items:**
    > 터미널에서 아래의 명령어를 실행하여 `uv`를 설치하세요:
    > Windows (PowerShell):
    ```bash
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
    > macOS/Linux:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
 
2. uv로 종속 항목 설치:

    > Note: uv는 자동으로 .venv를 생성하고 pyproject.toml에서 종속 항목을 설치합니다.
    > **Action Items**:
    > `agentic_ai/applications` 폴더로 이동한 후, 다음 명령어를 실행하여 종속 항목을 설치하세요:
    ```bash
    #  agentic_ai/applications 디렉토리로 이동
    cd agentic_ai/applications

    # Virtual Environment 생성 및 모든 종속 항목을 한 번에 설치
    uv sync
    ```

3. Create MCP Service

> **Action Items:**
> 아래 단계를 따라 `mcp_service.py` 파일을 코딩하여 백엔드 서비스를 생성하세요. 이를 통해 MCP 서버를 설정하고 실행하는 방법을 이해할 수 있습니다.

Note: 지금 `agentic_ai/applications` 폴더에 있다면, 먼저 루트 폴더로 돌아가세요:

```bash
cd ../..
```

3a: Import FastMCP

아래의 import 문을 `mcp_service.py` 파일 상단에 추가하세요:

    > Note: fastmcp는 Microsoft Agent Framework의 MCP 구현체입니다. MCP 서버를 쉽게 설정하고 실행할 수 있는 도구와 데코레이터를 제공합니다.
    > **Action Items:**
    > Note: fastmcp가 설치되어있지 않은 경우, `python -m pip install fastmcp` 명령어를 사용하여 설치하세요.
    
```python
from fastmcp import FastMCP
```

3b: Declare MCP

MCP 인스턴스를 `mcp_service.py` 파일에 아래와 같이 선언하세요. "insert FastMCP initialization code here"라는 키워드를 찾아 다음 코드로 교체합니다:

```python
mcp = FastMCP(
    name="Contoso Customer API as Tools",
    instructions=(
        "All customer, billing and knowledge data is accessible ONLY via the declared "
        "tools below.  Return values follow the pydanticschemas.  Always call the most "
        "specific tool that answers the user’s question."
    ),
    auth=auth,  
)
```

3c: Write MCP Tools

아래의 MCP 도구들을 `mcp_service.py` 파일에 추가하세요. 이 도구들은 고객 데이터와 상호작용하기 위한 엔드포인트를 정의합니다. "insert tool endpoint code here 1"라는 키워드를 찾아 다음 코드로 교체합니다:

**Tool 1: List All Customers**
```python
@mcp.tool(description="List all customers with basic info")
async def get_all_customers() -> List[CustomerSummary]:  
    data = await get_all_customers_async()
    return [CustomerSummary(**r) for r in data]
```

"insert tool endpoint code here 2"라는 키워드를 찾아 다음 코드로 교체합니다:

**Tool 2: Get Subscription Detail**

```python
@mcp.tool(  
    description=(  
        "Detailed subscription view → invoices (with payments) + service incidents."  
    )  
)  
async def get_subscription_detail(  
    subscription_id: Annotated[int, "Subscription identifier value"],  
) -> SubscriptionDetail:  
    data = await get_subscription_detail_async(subscription_id)

    # Convert nested data to Pydantic models
    invoices = []
    for inv_data in data['invoices']:
        payments = [Payment(**p) for p in inv_data['payments']]
        invoices.append(Invoice(**{**inv_data, 'payments': payments}))
    
    service_incidents = [ServiceIncident(**si) for si in data['service_incidents']]
    
    return SubscriptionDetail(**{**data, 'invoices': invoices, 'service_incidents': service_incidents})
```

3d: Run MCP Server

마지막으로, `mcp_service.py` 파일 하단에 "insert Run MCP Server code here"라는 키워드를 찾아 다음 코드를 추가하여 MCP 서버를 시작하세요:

```python
if __name__ == "__main__":  
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=8000))  
```

4. Start MCP Server

    > **Action Items:**
    > Note: 지금 `agentic_ai/applications` 폴더에 있다면, 먼저 루트 폴더로 돌아가세요:
    ```bash
    cd ../..
    ```
    > `mcp` 폴더로 이동한 후 MCP 서버를 시작하세요:
    ```bash
    cd mcp
    uv run python mcp_service.py
    ```
    > Note: 이 터미널 창에서 MCP 서버를 실행 상태로 유지하세요. 다음 단계로 진행하려면 새 터미널 창을 열어주세요. 
    
    <img src="media/01_mcp_fastmcp.jpg" />

## FastMCP 오류
    > pip install fastmcp를 하셔도 혹시 uv가 fastmcp를 못 찾는 경우, fastmcp가 설치된 환경과 현재 vs code에서 연결된 python환경과 다르기 때문입니다  
    > 파이썬이 도는 경로를 찾아서 명시적으로 mcp_service.py를 실행시켜 주세요
    
    > python -c "import sys; print(sys.executable)"

    ```
    uv run --python "C:\Users\xxxxx\AppData\Local\Programs\Python\Python313\python.exe" mcp_service.py
    ```
 
## 성공 기준

- MCP 서버가 실행 중이며 요청을 받을 준비가 되어 있습니다.
- MCP 서버 상태를 확인하기 위한 샘플 powershell 명령어:  
    ```powershell
    Invoke-WebRequest -Uri "http://localhost:8000/mcp" -Method POST -Headers @{Accept="application/json, text/event-stream";"Content-Type"="application/json"} -Body               '{"jsonrpc":"2.0","id":"init-1","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"8"}}}'
    ```

    <img src="media/01_mcp_local_ok.jpg" />
    
    **Note:** 이것은 MCP 서버 엔드포인트이며 브라우저나 SSE와 같은 지원되지 않는 전송 방식으로 직접 접근할 수 없으므로 스트리밍 가능한 HTTP 전송 방식을 사용하세요. 아래의 오류는 브라우저에서 예상되는 동작입니다.
  
    <img src="media/01_mcp_localhost_err.png" />

 - MCP 서버가 온라인 상태인지 확인하기 위한 샘플 curl 명령어:
    ```bash
    curl -sS -i -X POST "http://localhost:8000/mcp" -H "Accept: application/json, text/event-stream" -H 'Content-Type: application/json'  --data '{"jsonrpc":"2.0","id":"init-            1","method":"initialize", "params":{"protocolVersion":"2024-11-05","capabilities":{}, "clientInfo":{"name":"curl","version":"8"}}}'`
    ```

## 다음 단계: Backend Server

* [Hands-on Lab 2 – Backend](2_02_backend_uv.md)

## 실습 순서

### Part 1
* [Microsoft Agent Framework Basic Concept HoL](00_basic_concept.md)

### Part 2
* [Hands-on Lab 0 – Setup](2_00_setup.md)
* [Hands-on Lab 1 – MCP Server](2_01_mcp_uv.md)
* [Hands-on Lab 2 – Backend](2_02_backend_uv.md)
* [Hands-on Lab 3 – Frontend](2_03_frontend_react.md)




