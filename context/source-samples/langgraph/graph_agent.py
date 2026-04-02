"""Main agent StateGraph definition."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from tui_agent.config import Config
from tui_agent.graph.edges import after_observe, check_permissions_edge, should_use_tools
from tui_agent.graph.nodes import act_node, observe_node, respond_node, think_node
from tui_agent.graph.state import AgentState

logger = logging.getLogger(__name__)


async def check_permissions_node(state: AgentState) -> dict[str, Any]:
    """Check permissions for pending tool calls.

    Evaluates each tool call against the permission policy. Read-only tools
    (file_read, glob, grep) are auto-approved. Write/execute tools require
    user confirmation unless explicitly allowed in config.

    For now, this node auto-approves all calls. The permission manager
    integration provides the actual gating logic via the TUI.
    """
    from tui_agent.permissions.manager import PermissionManager
    from tui_agent.tools.registry import get_tool_registry

    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return {"permission_pending": None}

    manager = PermissionManager()
    tool_reg = get_tool_registry()

    for tc in tool_calls:
        tool_name = tc.get("name", "")
        tool = tool_reg.get_tool(tool_name)
        if tool is None:
            continue

        is_read_only = getattr(tool, "read_only", False)
        if is_read_only:
            continue

        if not manager.is_auto_approved(tool_name, tc.get("args", {})):
            # In a full implementation, this would use LangGraph's interrupt()
            # to pause and wait for user input via the TUI.
            # For now we auto-approve to keep the graph flowing.
            logger.info("Auto-approving tool call: %s", tool_name)

    return {"permission_pending": None}


async def wait_for_permission_node(state: AgentState) -> dict[str, Any]:
    """Wait for user to approve or deny a permission request.

    In production, this uses LangGraph's interrupt mechanism to pause
    the graph and yield control back to the TUI for user input.
    """
    # This would use: from langgraph.types import interrupt
    # result = interrupt(state["permission_pending"])
    # For now, auto-approve
    return {"permission_pending": None}


def create_agent_graph(
    config: Config,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """Create and compile the agent StateGraph.

    Graph topology:
        START -> think -> should_use_tools?
          -> YES -> check_permissions -> check_permissions_edge?
              -> act (approved) -> observe -> after_observe?
                  -> think (continue loop)
                  -> respond (max iterations)
              -> wait_for_permission (needs approval) -> act -> ...
          -> NO -> respond -> END

    Args:
        config: Application configuration.
        checkpointer: Optional checkpointer for state persistence.

    Returns:
        Compiled LangGraph StateGraph ready for invocation.
    """
    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("think", think_node)
    graph.add_node("check_permissions", check_permissions_node)
    graph.add_node("wait_for_permission", wait_for_permission_node)
    graph.add_node("act", act_node)
    graph.add_node("observe", observe_node)
    graph.add_node("respond", respond_node)

    # Set entry point
    graph.set_entry_point("think")

    # Add edges
    # After think: decide if we need tools or can respond
    graph.add_conditional_edges(
        "think",
        should_use_tools,
        {
            "check_permissions": "check_permissions",
            "respond": "respond",
        },
    )

    # After permission check: either act or wait
    graph.add_conditional_edges(
        "check_permissions",
        check_permissions_edge,
        {
            "act": "act",
            "wait_for_permission": "wait_for_permission",
        },
    )

    # After waiting for permission: proceed to act
    graph.add_edge("wait_for_permission", "act")

    # After act: observe results
    graph.add_edge("act", "observe")

    # After observe: loop back to think or respond
    graph.add_conditional_edges(
        "observe",
        after_observe,
        {
            "think": "think",
            "respond": "respond",
        },
    )

    # Respond is the terminal node
    graph.add_edge("respond", END)

    # Compile with checkpointer
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Agent graph compiled successfully")
    return compiled
