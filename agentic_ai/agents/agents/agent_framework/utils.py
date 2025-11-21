"""
Common utilities for agent framework patterns.

This module contains shared utilities used across different multi-agent patterns
including handoff routing and magentic orchestration.
"""

import logging
from typing import Any, List, Set

from agent_framework import MCPStreamableHTTPTool

logger = logging.getLogger(__name__)


class FilteredMCPTool:
    """
    Wrapper around MCPStreamableHTTPTool that filters functions based on allowed tool names.
    
    This allows each agent to have access only to their specific tools,
    preventing unauthorized tool access and keeping agents focused on their domain.
    
    Example usage:
        ```python
        # Connect to MCP server once
        base_mcp_tool = MCPStreamableHTTPTool(url="http://localhost:8000")
        await base_mcp_tool.__aenter__()
        
        # Create filtered wrappers for different agents
        billing_tools = FilteredMCPTool(
            mcp_tool=base_mcp_tool,
            allowed_tool_names=["get_customer_detail", "get_billing_summary", ...]
        )
        billing_tools.filter_functions()
        
        # Pass filtered functions to agent
        agent = ChatAgent(..., tools=billing_tools.functions)
        ```
    """
    
    def __init__(self, mcp_tool: MCPStreamableHTTPTool, allowed_tool_names: List[str]) -> None:
        """
        Initialize filtered MCP tool wrapper.
        
        Args:
            mcp_tool: The underlying MCP tool with all functions loaded
            allowed_tool_names: List of tool names this agent is allowed to use
        """
        self._mcp_tool = mcp_tool
        self._allowed_tool_names: Set[str] = set(allowed_tool_names)
        self._filtered_functions: List[Any] = []
        
    def filter_functions(self) -> None:
        """
        Filter the MCP tool's functions to only include allowed ones.
        
        This method should be called after the MCP tool has connected and loaded its functions.
        Logs a warning if no functions are loaded yet or if no matching tools are found.
        """
        if not self._mcp_tool.functions:
            logger.warning(
                "[FilteredMCPTool] MCP tool has no functions loaded yet. "
                "Ensure the tool is connected before filtering."
            )
            return
            
        self._filtered_functions = [
            func for func in self._mcp_tool.functions
            if func.name in self._allowed_tool_names
        ]
        
        if not self._filtered_functions:
            logger.warning(
                f"[FilteredMCPTool] No matching tools found! "
                f"Allowed: {self._allowed_tool_names}, "
                f"Available: {[f.name for f in self._mcp_tool.functions]}"
            )
        else:
            logger.info(
                f"[FilteredMCPTool] Filtered {len(self._filtered_functions)} tools from "
                f"{len(self._mcp_tool.functions)} available. "
                f"Allowed: {sorted(self._allowed_tool_names)}"
            )
    
    @property
    def functions(self) -> List[Any]:
        """
        Return the filtered list of functions.
        
        Returns:
            List of AIFunction objects that match the allowed tool names
        """
        return self._filtered_functions
    
    async def __aenter__(self) -> "FilteredMCPTool":
        """
        Enter async context - connects underlying MCP tool and filters functions.
        
        Note: If the underlying MCP tool is already connected, this won't reconnect it.
        """
        await self._mcp_tool.__aenter__()
        self.filter_functions()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """
        Exit async context - closes underlying MCP tool.
        
        Warning: This will close the underlying MCP connection. If multiple agents
        share the same base MCP tool, closing one will affect all others.
        """
        await self._mcp_tool.__aexit__(exc_type, exc_value, traceback)


def create_filtered_tool_list(
    base_mcp_tool: MCPStreamableHTTPTool | None,
    allowed_tool_names: List[str],
    agent_name: str = "unknown"
) -> List[Any] | None:
    """
    Helper function to create a filtered tool list from a base MCP tool.
    
    This is a convenience function that encapsulates the filtering pattern
    used across different agent implementations.
    
    Args:
        base_mcp_tool: The base MCP tool with all functions loaded (or None)
        allowed_tool_names: List of tool names to allow for this agent
        agent_name: Name of the agent (for logging purposes)
        
    Returns:
        List of filtered AIFunction objects, or None if base_mcp_tool is None
        
    Example:
        ```python
        base_tool = MCPStreamableHTTPTool(url="http://localhost:8000")
        await base_tool.__aenter__()
        
        billing_tools = create_filtered_tool_list(
            base_mcp_tool=base_tool,
            allowed_tool_names=["get_customer_detail", "pay_invoice"],
            agent_name="crm_billing"
        )
        
        agent = ChatAgent(..., tools=billing_tools)
        ```
    """
    if base_mcp_tool is None:
        logger.info(f"[FilteredMCPTool] No MCP tool provided for agent '{agent_name}'")
        return None
    
    filtered_wrapper = FilteredMCPTool(
        mcp_tool=base_mcp_tool,
        allowed_tool_names=allowed_tool_names
    )
    filtered_wrapper.filter_functions()
    
    logger.debug(
        f"[FilteredMCPTool] Created filtered tool list for agent '{agent_name}' "
        f"with {len(filtered_wrapper.functions)} tools"
    )
    
    return filtered_wrapper.functions
