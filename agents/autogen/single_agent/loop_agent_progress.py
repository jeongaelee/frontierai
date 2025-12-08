# agents/autogen/single_agent/loop_agent.py
import os
import asyncio
from typing import Any, Callable, Awaitable, Optional, Mapping, List

from dotenv import load_dotenv

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMessageTermination
from autogen_core import CancellationToken
from autogen_core.tools import BaseTool
from autogen_core.utils import schema_to_pydantic_model
from pydantic import BaseModel

from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

from agents.base_agent import BaseAgent
import mcp
from fastmcp.exceptions import ToolError



load_dotenv()


# A simple Pydantic model for the return value (BaseTool requires a BaseModel return type)
class ToolTextResult(BaseModel):
    text: str

ProgressSink = Callable[[dict], Awaitable[None]]

class MCPProgressTool(BaseTool[BaseModel, ToolTextResult]):
    """
    Wrap a remote MCP tool so Autogen sees it as a local tool, while forwarding progress updates.
    """

    def __init__(
        self,
        client: Client,
        mcp_tool: mcp.types.Tool,
        progress_sink: Optional[ProgressSink] = None,
    ) -> None:
        # Build a Pydantic args model from the MCP tool's JSON schema
        args_model = schema_to_pydantic_model(mcp_tool.inputSchema)
        super().__init__(
            args_type=args_model,
            return_type=ToolTextResult,
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            strict=False,  # set True if you want to enforce no extra args/defaults
        )
        self._client = client
        self._tool_name = mcp_tool.name
        self._progress_sink = progress_sink

    async def run(self, args: BaseModel, cancellation_token: CancellationToken) -> ToolTextResult:
        # Serialize args excluding unset values so we only send what's provided
        kwargs: Mapping[str, Any] = args.model_dump(exclude_unset=True)

        async def progress_cb(progress: float, total: float | None, message: str | None):
            if not self._progress_sink:
                return
            try:
                pct = int((progress / total) * 100) if total else int(progress)
            except Exception:
                pct = int(progress)
            await self._progress_sink({
                "type": "progress",
                "tool": self._tool_name,
                "percent": pct,
                "message": message or "",
            })

        # Use a fresh session for each tool call to avoid cross-call state pollution
        async with self._client.new() as c:
            call_coro = c.call_tool_mcp(
                name=self._tool_name,
                arguments=dict(kwargs),
                progress_handler=progress_cb,
            )
            task = asyncio.create_task(call_coro)
            # If CancellationToken exposes a way to bind, hook it here. Otherwise, just check state:
            if cancellation_token.is_cancelled():
                task.cancel()
                raise asyncio.CancelledError("Operation cancelled")

            try:
                result: mcp.types.CallToolResult = await task
            except asyncio.CancelledError:
                # Propagate cancellation
                raise

            if result.isError:
                # Bubble up MCP tool error for Autogen to surface
                msg = ""
                try:
                    msg = (result.content[0].text if result.content else "Tool error")
                except Exception:
                    msg = "Tool error"
                raise ToolError(msg)

            # Aggregate text contents; adjust as needed if you want images/resources
            texts: list[str] = []
            for content in result.content:
                if isinstance(content, mcp.types.TextContent):
                    texts.append(content.text)
            final_text = "\n".join(texts) if texts else "(no text content)"
            return ToolTextResult(text=final_text)

    # Provide a readable string for the tool’s result (what the LLM “sees” in logs/streams)
    def return_value_as_string(self, value: Any) -> str:
        try:
            if isinstance(value, ToolTextResult):
                return value.text
        except Exception:
            pass
        return super().return_value_as_string(value)




class Agent(BaseAgent):
    def __init__(self, state_store, session_id, access_token: str | None = None) -> None:
        super().__init__(state_store, session_id)
        self.loop_agent = None
        self._initialized = False
        self._access_token = access_token
        self._progress_sink: Optional[Callable[[dict], Awaitable[None]]] = None  # side-channel sink

    def set_progress_sink(self, sink: Optional[Callable[[dict], Awaitable[None]]]) -> None:
        """Install (or remove) a per-call async sink to receive side-channel tool progress events."""
        self._progress_sink = sink

    async def _build_mcp_progress_tools(self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        auth: Optional[str] = None,   # "Bearer <token>" or fastmcp.client.auth.BearerAuth
        progress_sink: Optional[ProgressSink] = None,
    ) -> List[MCPProgressTool]:
        """
        Create progress-aware Autogen tools for every remote MCP tool at the given endpoint.
        """
        transport = StreamableHttpTransport(url, headers=headers, auth=auth)

        client = Client(transport=transport)
        async with client:
            tools_resp = await client.list_tools_mcp()
            adapters: List[MCPProgressTool] = []
            for mcp_tool in tools_resp.tools:
                adapters.append(MCPProgressTool(client, mcp_tool, progress_sink))
            return adapters


    async def _setup_loop_agent(self) -> None:
        """Initialize the assistant and loop agent once, using our progress-aware tools."""
        if self._initialized:
            return

        # Build tools with progress support
        tools = await self._build_mcp_progress_tools(
            url=self.mcp_server_uri,
            headers={"Authorization": f"Bearer {self._access_token}"} if self._access_token else None,
            progress_sink=self._progress_sink,
        )

        # Set up the OpenAI/Azure model client
        model_client = AzureOpenAIChatCompletionClient(
            api_key=self.azure_openai_key,
            azure_endpoint=self.azure_openai_endpoint,
            api_version=self.api_version,
            azure_deployment=self.azure_deployment,
            model=self.openai_model_name,
        )

        # Set up the assistant agent
        agent = AssistantAgent(
            name="ai_assistant",
            model_client=model_client,
            tools=tools,
            system_message=(
                "You are a helpful assistant. You can use tools to get work done. "
                "Provide progress when running long operations."
            ),
        )

        termination_condition = TextMessageTermination("ai_assistant")

        self.loop_agent = RoundRobinGroupChat(
            [agent],
            termination_condition=termination_condition,
        )

        if self.state:
            await self.loop_agent.load_state(self.state)
        self._initialized = True

    async def chat_async(self, prompt: str) -> str:
        """Backwards-compatible single-shot call."""
        await self._setup_loop_agent()
        response = await self.loop_agent.run(task=prompt, cancellation_token=CancellationToken())
        assistant_response = response.messages[-1].content

        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": assistant_response}
        ]
        self.append_to_chat_history(messages)

        new_state = await self.loop_agent.save_state()
        self._setstate(new_state)

        return assistant_response

    async def chat_stream(self, prompt: str):
        """
        Async generator that yields Autogen streaming events while processing prompt.
        Backend will consume this and forward to frontend.
        """
        await self._setup_loop_agent()
        stream = self.loop_agent.run_stream(task=prompt, cancellation_token=CancellationToken())

        async for event in stream:
            yield event

        # After run finishes, persist state
        new_state = await self.loop_agent.save_state()
        self._setstate(new_state)