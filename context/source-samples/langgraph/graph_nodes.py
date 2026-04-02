"""Graph nodes: think, act, observe, respond."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tui_agent.graph.state import AgentState
from tui_agent.llm.registry import get_provider_registry
from tui_agent.tools.registry import get_tool_registry
from tui_agent.utils.cost import calculate_cost
from tui_agent.utils.tokens import count_message_tokens

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert coding assistant running inside a terminal TUI. You help users \
with software development tasks by reading, writing, and editing files, running \
shell commands, searching code, and more.

Guidelines:
- Be concise and direct in your responses.
- When modifying files, show what you changed and why.
- Use tools to gather information before making changes.
- Ask for clarification when requirements are ambiguous.
- Prefer safe, non-destructive operations.
- When running shell commands, explain what they do.
- Current working directory: {working_directory}
"""


async def think_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM with the current messages and available tool schemas.

    This is the core reasoning node. It sends the conversation history
    plus tool definitions to the LLM and receives a response that may
    contain text, tool calls, or both.

    Returns:
        State update with new AI message, any tool_calls extracted,
        and updated token/cost counters.
    """
    provider_name = state.get("current_provider", "anthropic")
    model_name = state.get("current_model", "claude-sonnet-4-20250514")
    working_dir = state.get("working_directory", ".")

    registry = get_provider_registry()
    provider = registry.get_provider(provider_name)
    if provider is None:
        return {
            "error": f"Provider '{provider_name}' not available. Check API key.",
            "tool_calls": [],
        }

    llm = provider.get_chat_model(model_name)

    # Bind tools
    tool_registry = get_tool_registry()
    tools = tool_registry.get_langchain_tools()
    if tools:
        llm = llm.bind_tools(tools)

    # Build messages with system prompt
    system_msg = SystemMessage(content=SYSTEM_PROMPT.format(working_directory=working_dir))
    messages = [system_msg] + list(state.get("messages", []))

    try:
        response: AIMessage = await llm.ainvoke(messages)
    except Exception as e:
        logger.error("LLM invocation failed: %s", e)
        return {
            "messages": [AIMessage(content=f"Error calling LLM: {e}")],
            "tool_calls": [],
            "error": str(e),
        }

    # Extract tool calls
    tool_calls: list[dict[str, Any]] = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": tc.get("name", ""),
                "args": tc.get("args", {}),
            })

    # Token counting
    input_tokens = count_message_tokens(messages, model_name)
    output_tokens = count_message_tokens([response], model_name)
    total_turn_tokens = input_tokens + output_tokens
    cost = calculate_cost(model_name, input_tokens, output_tokens)

    return {
        "messages": [response],
        "tool_calls": tool_calls,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "turn_tokens": state.get("turn_tokens", 0) + total_turn_tokens,
        "turn_cost": state.get("turn_cost", 0.0) + cost,
        "total_tokens": state.get("total_tokens", 0) + total_turn_tokens,
        "total_cost": state.get("total_cost", 0.0) + cost,
        "error": None,
    }


async def act_node(state: AgentState) -> dict[str, Any]:
    """Execute pending tool calls.

    Iterates over each tool call in state, invokes the corresponding
    tool, and collects results.

    Returns:
        State update with tool_results populated and tool_calls cleared.
    """
    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return {"tool_results": [], "tool_calls": []}

    tool_registry = get_tool_registry()
    results: list[dict[str, Any]] = []

    for tc in tool_calls:
        tool_name = tc.get("name", "")
        tool_args = tc.get("args", {})
        tool_id = tc.get("id", "")

        tool = tool_registry.get_tool(tool_name)
        if tool is None:
            results.append({
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": f"Error: Tool '{tool_name}' not found.",
                "is_error": True,
            })
            continue

        # Inject working directory for tools that need it
        working_dir = state.get("working_directory", ".")
        if "working_directory" not in tool_args and hasattr(tool, "requires_working_dir"):
            tool_args["working_directory"] = working_dir

        try:
            result = await tool.ainvoke(tool_args)
            content = str(result) if result is not None else "Done (no output)."
            # Truncate very large outputs
            if len(content) > 50_000:
                content = content[:50_000] + "\n... [output truncated at 50,000 chars]"
            results.append({
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": content,
                "is_error": False,
            })
        except Exception as e:
            logger.error("Tool '%s' failed: %s", tool_name, e)
            results.append({
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": f"Error executing {tool_name}: {e}",
                "is_error": True,
            })

    return {"tool_results": results, "tool_calls": []}


async def observe_node(state: AgentState) -> dict[str, Any]:
    """Convert tool results into ToolMessages for the conversation.

    Takes the raw tool_results from the act node and creates proper
    LangChain ToolMessage objects that the LLM can process.

    Returns:
        State update with new ToolMessages added to messages, tool_results cleared.
    """
    tool_results = state.get("tool_results", [])
    if not tool_results:
        return {"messages": [], "tool_results": []}

    messages: list[ToolMessage] = []
    for result in tool_results:
        messages.append(
            ToolMessage(
                content=result["content"],
                tool_call_id=result["tool_call_id"],
                name=result["name"],
            )
        )

    return {"messages": messages, "tool_results": []}


async def respond_node(state: AgentState) -> dict[str, Any]:
    """Final node: reset per-turn counters for the next user turn.

    Returns:
        State update resetting iteration_count and turn counters.
    """
    return {
        "iteration_count": 0,
        "turn_tokens": 0,
        "turn_cost": 0.0,
        "error": None,
    }
