"""Agent state definition for the LangGraph StateGraph."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State flowing through the agent graph.

    Attributes:
        messages: Conversation message history (auto-merged via add_messages reducer).
        tool_calls: Pending tool calls from the LLM response.
        tool_results: Results from executed tools, fed back to the LLM.
        current_model: Active model identifier (e.g. 'claude-sonnet-4-20250514').
        current_provider: Active provider name (e.g. 'anthropic').
        working_directory: Current working directory for file/shell operations.
        permission_pending: Tool call awaiting user permission approval, or None.
        iteration_count: Number of think-act-observe loops in the current turn.
        total_tokens: Cumulative token usage across the session.
        total_cost: Cumulative cost in USD across the session.
        turn_tokens: Token usage for the current turn only.
        turn_cost: Cost for the current turn only.
        error: Last error message if any, cleared on next successful step.
        metadata: Arbitrary metadata for extensibility.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    current_model: str
    current_provider: str
    working_directory: str
    permission_pending: Optional[dict[str, Any]]
    iteration_count: int
    total_tokens: int
    total_cost: float
    turn_tokens: int
    turn_cost: float
    error: Optional[str]
    metadata: dict[str, Any]


def create_initial_state(
    model: str = "claude-sonnet-4-20250514",
    provider: str = "anthropic",
    working_directory: str = ".",
) -> dict[str, Any]:
    """Create the initial state dictionary for a new agent session.

    Args:
        model: Default model identifier.
        provider: Default provider name.
        working_directory: Starting working directory.

    Returns:
        Dictionary matching AgentState schema with sensible defaults.
    """
    return {
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_model": model,
        "current_provider": provider,
        "working_directory": working_directory,
        "permission_pending": None,
        "iteration_count": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "turn_tokens": 0,
        "turn_cost": 0.0,
        "error": None,
        "metadata": {},
    }
