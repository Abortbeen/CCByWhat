"""Core agent loop using LangChain create_agent (v1.2+)."""

from __future__ import annotations

import asyncio
import queue
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver

from tui_agent.agent.callbacks import StreamEvent, TUIStreamingCallback
from tui_agent.agent.prompts import build_memory_context, build_system_prompt
from tui_agent.config import Config
from tui_agent.llm.registry import create_llm
from tui_agent.memory.persistent import PersistentMemory
from tui_agent.tools.registry import create_all_tools
from tui_agent.utils.cost import CostTracker


class AgentRunner:
    """Manages the LangChain agent lifecycle and execution.

    Uses the new LangChain v1.2+ `create_agent` API which returns a
    compiled LangGraph StateGraph under the hood.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cost_tracker = CostTracker(config)
        self.callback = TUIStreamingCallback()
        self.persistent_memory = PersistentMemory()
        self._llm: BaseChatModel | None = None
        self._tools: list[BaseTool] = []
        self._graph: Any = None
        self._checkpointer = MemorySaver()
        self._thread_id: str = "default"

    def initialize(self) -> None:
        """Initialize the LLM, tools, and agent graph."""
        self._llm = create_llm(
            provider=self.config.provider or "anthropic",
            model=self.config.model or "claude-sonnet-4-20250514",
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            streaming=True,
            callbacks=[self.callback],
        )
        self._tools = create_all_tools(self.config)
        self._build_graph()

    def _build_graph(self) -> None:
        """Build the LangChain agent graph using create_agent."""
        if self._llm is None:
            raise RuntimeError("LLM not initialized. Call initialize() first.")

        memory_context = build_memory_context(self.persistent_memory.load())
        system_prompt = build_system_prompt(self.config.working_directory)
        full_system = system_prompt
        if memory_context:
            full_system = f"{system_prompt}\n\n{memory_context}"

        self._graph = create_agent(
            model=self._llm,
            tools=self._tools,
            system_prompt=full_system,
            checkpointer=self._checkpointer,
        )

    async def run(self, user_input: str) -> str:
        """Run the agent with user input and return the final response.

        Args:
            user_input: The user's message.

        Returns:
            The agent's final text response.
        """
        if self._graph is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        try:
            config = {
                "configurable": {"thread_id": self._thread_id},
                "callbacks": [self.callback],
            }
            result = await self._graph.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )

            # Extract final AI message
            messages = result.get("messages", [])
            output = ""
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    output = self._extract_text(msg.content)
                    break

            # Track costs
            usage = self.callback.get_usage()
            self.cost_tracker.add_usage(
                input_tokens=usage["total_input_tokens"],
                output_tokens=usage["total_output_tokens"],
            )

            return output

        except Exception as e:
            error_msg = f"Agent error: {e}"
            self.callback.queue.put(
                StreamEvent(event_type="error", content=error_msg)
            )
            return error_msg

    async def run_streaming(self, user_input: str) -> None:
        """Run the agent with streaming output via the callback queue.

        The TUI should consume events from self.callback.queue.

        Args:
            user_input: The user's message.
        """
        if self._graph is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        try:
            config = {
                "configurable": {"thread_id": self._thread_id},
                "callbacks": [self.callback],
            }
            await self._graph.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )
        except Exception as e:
            self.callback.queue.put(
                StreamEvent(event_type="error", content=f"Agent error: {e}")
            )
        finally:
            self.callback.queue.put(StreamEvent(event_type="complete"))

    def switch_model(self, provider: str, model: str) -> None:
        """Switch to a different LLM provider and model.

        Args:
            provider: The provider name (anthropic, openai, google, ollama).
            model: The model identifier.
        """
        self.config.provider = provider
        self.config.model = model
        self.initialize()

    def clear_history(self) -> None:
        """Clear conversation history by switching to a new thread."""
        import uuid
        self._thread_id = str(uuid.uuid4())

    def compact_history(self, keep_last_n: int = 10) -> None:
        """Compact conversation history.

        Note: With the new create_agent API using checkpointer,
        compaction is handled by starting a new thread with summary.

        Args:
            keep_last_n: Number of recent message pairs to keep.
        """
        # For now, simply reset the thread (full compaction)
        # A more sophisticated approach would summarize and carry forward
        self.clear_history()

    @staticmethod
    def _extract_text(content: Any) -> str:
        """Extract plain text from LLM content (handles str, list of dicts, etc.)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
                elif hasattr(block, "text"):
                    parts.append(str(block.text))
            return "".join(parts)
        return str(content)

    def add_tools(self, new_tools: list[BaseTool]) -> None:
        """Add additional tools (e.g. from MCP) and rebuild the graph.

        Args:
            new_tools: List of tools to add.
        """
        self._tools.extend(new_tools)
        self._build_graph()

    @property
    def event_queue(self) -> queue.Queue[StreamEvent]:
        """Return the streaming event queue."""
        return self.callback.queue

    @property
    def tools(self) -> list[BaseTool]:
        """Return the list of available tools."""
        return self._tools

    @property
    def model_name(self) -> str:
        """Return the current model name."""
        return self.config.model or "unknown"

    @property
    def provider_name(self) -> str:
        """Return the current provider name."""
        return self.config.provider or "unknown"
