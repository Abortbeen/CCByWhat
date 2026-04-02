"""Main REPL application - Claude Code style terminal interface using LangGraph."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from tui_agent.config import Config
from tui_agent.mcp.client import MCPManager
from tui_agent.mcp.tool_bridge import create_mcp_tools
from tui_agent.skills.builtin import register_builtin_skills
from tui_agent.skills.registry import get_skills_registry
from tui_agent.utils.cost import calculate_cost, format_cost


class TUIAgentApp:
    """Claude Code style REPL terminal agent powered by LangGraph."""

    def __init__(self, config: Config, resume_thread: str | None = None, **kwargs: Any) -> None:
        self.config = config
        self.console = Console()
        self._is_processing = False
        self._session_start = time.time()
        self._tool_count = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        self._history: list[str] = []
        self._graph: Any = None
        self._thread_id: str = resume_thread or "default"
        self._current_model = config.default_model
        self._current_provider = config.default_provider
        self._mcp_manager = MCPManager()
        self._skills_registry = get_skills_registry()

    def run(self) -> None:
        """Main REPL loop."""
        self.console.clear()
        self._print_welcome()

        # Initialize agent graph
        self.console.print("[dim]Initializing LangGraph agent...[/dim]")
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._initialize())

            # Initialize MCP servers
            mcp_servers = self.config.get_mcp_servers()
            if mcp_servers:
                self.console.print(f"[dim]Connecting to {len(mcp_servers)} MCP server(s)...[/dim]")
                connected = loop.run_until_complete(self._mcp_manager.connect_all(mcp_servers))
                if connected > 0:
                    # MCP tools are registered into the tool registry
                    mcp_tools = create_mcp_tools(self._mcp_manager)
                    from tui_agent.tools.registry import get_tool_registry
                    tool_reg = get_tool_registry()
                    for t in mcp_tools:
                        tool_reg.register(t)
                    self.console.print(
                        f"[green]MCP:[/green] {connected} server(s), {self._mcp_manager.tool_count} tools"
                    )

            loop.close()

            # Initialize skills
            register_builtin_skills()
            from pathlib import Path
            user_skills_dir = Path(self.config.config_dir) / "skills"
            self._skills_registry.load_from_directory(user_skills_dir)

            self.console.print(
                f"[green]Ready![/green] Model: [bold cyan]{self._current_provider}:{self._current_model}[/bold cyan]"
                f" | Skills: {len(self._skills_registry.list_skills())}"
                f" | MCP: {self._mcp_manager.tool_count} tools\n"
            )
        except Exception as e:
            self.console.print(f"[red]Failed to initialize: {e}[/red]")
            self.console.print("[dim]Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY[/dim]")
            return

        # REPL loop
        while True:
            try:
                user_input = self._get_input()
                if user_input is None:
                    break
                if not user_input.strip():
                    continue

                self._history.append(user_input)

                # Handle slash commands
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                # Run agent
                self._run_agent(user_input)

            except KeyboardInterrupt:
                if self._is_processing:
                    self.console.print("\n[yellow]Interrupted.[/yellow]")
                    self._is_processing = False
                else:
                    self.console.print("\n[dim]Press Ctrl+C again or type /exit to quit[/dim]")
                    try:
                        time.sleep(0.5)
                    except KeyboardInterrupt:
                        self.console.print("\n[dim]Goodbye![/dim]")
                        break
            except EOFError:
                self.console.print("\n[dim]Goodbye![/dim]")
                break

    async def _initialize(self) -> None:
        """Initialize the LangGraph agent graph."""
        from tui_agent.graph.agent import create_agent_graph
        from tui_agent.graph.checkpointer import create_checkpointer

        checkpointer = await create_checkpointer(self.config.db_path)
        self._graph = create_agent_graph(self.config, checkpointer)

    def _print_welcome(self) -> None:
        """Print welcome banner."""
        self.console.print(
            Panel(
                "[bold]TUI Code Agent[/bold] - LangGraph-powered coding assistant\n"
                "[dim]Type a message, /help for commands, Ctrl+C twice to exit[/dim]",
                border_style="blue",
            )
        )

    def _get_branch(self) -> str:
        """Get current git branch (sync)."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, timeout=5
            )
            branch = result.stdout.strip()
            return branch if branch else "no-git"
        except Exception:
            return "no-git"

    def _get_input(self) -> str | None:
        """Get user input with prompt.

        Layout (matches Claude Code style):
          ────────────────────────────────────────
          ❯ <user types here>
          ────────────────────────────────────────
            branch:master
            claude-opus-4-6 | session:24s | ... | 🔧3
        """
        sep = "─" * 40
        status_lines = self._build_status_lines()
        # Pre-print: top sep, prompt, bottom sep, status bar
        # Then move cursor back up to the prompt line
        lines_below = 1 + len(status_lines)  # bottom sep + status lines
        self.console.print(f"  [dim]{sep}[/dim]")
        sys.stdout.write("  ❯ \n")
        sys.stdout.write(f"  {sep}\n")
        for sl in status_lines:
            sys.stdout.write(f"{sl}\n")
        # Move cursor back up to prompt line, column 5
        sys.stdout.write(f"\x1b[{lines_below + 1}A\x1b[5C")
        sys.stdout.flush()
        try:
            user_input = input()
        except (EOFError, KeyboardInterrupt):
            sys.stdout.write(f"\x1b[{lines_below}B\n")
            sys.stdout.flush()
            raise
        # Move past pre-printed lines below
        sys.stdout.write(f"\x1b[{lines_below}E")
        sys.stdout.flush()
        return user_input

    def _build_status_lines(self) -> list[str]:
        """Build the status bar text lines (plain strings for pre-printing)."""
        branch = self._get_branch()
        elapsed = int(time.time() - self._session_start)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}m{secs:02d}s" if mins else f"{secs}s"

        if self._total_tokens > 1000:
            token_str = f"{self._total_tokens/1000:.1f}k"
        else:
            token_str = str(self._total_tokens)

        line1 = f"    branch:{branch}"
        line2 = f"    {self._current_model} | session:{time_str} | tokens:{token_str} | {format_cost(self._total_cost)} | 🔧{self._tool_count}"
        return [line1, line2]

    def _run_agent(self, user_input: str) -> None:
        """Run the agent graph and display streaming response."""
        self._is_processing = True

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._run_agent_async(user_input))
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Interrupted.[/yellow]")
        except Exception as e:
            self.console.print(f"\n  [red]Agent error: {e}[/red]")
        finally:
            loop.close()
            self._is_processing = False

    async def _run_agent_async(self, user_input: str) -> None:
        """Run the LangGraph agent with streaming output."""
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        if self._graph is None:
            self.console.print("[red]Agent not initialized.[/red]")
            return

        graph_config = {"configurable": {"thread_id": self._thread_id}}
        inputs = {
            "messages": [HumanMessage(content=user_input)],
            "current_model": self._current_model,
            "current_provider": self._current_provider,
            "working_directory": self.config.working_directory,
        }

        response_text = ""
        first_token = True

        with Live(
            Spinner("dots", text="[bold cyan]Brewing...[/bold cyan]"),
            console=self.console,
            refresh_per_second=10,
            transient=True,
        ) as live:
            spinner_active = True
            try:
                async for event in self._graph.astream_events(
                    inputs, config=graph_config, version="v2"
                ):
                    kind = event.get("event", "")

                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content"):
                            content = chunk.content
                            # Handle both str and list content blocks
                            text = ""
                            if isinstance(content, str):
                                text = content
                            elif isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict):
                                        text += block.get("text", "")
                                    elif isinstance(block, str):
                                        text += block
                                    elif hasattr(block, "text"):
                                        text += str(block.text)

                            if text:
                                if first_token:
                                    first_token = False
                                    live.stop()
                                    spinner_active = False
                                response_text += text
                                print(text, end="", flush=True)

                    elif kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        self._tool_count += 1
                        if spinner_active:
                            live.update(
                                Spinner("dots", text=f"[bold cyan]Running {tool_name}...[/bold cyan]")
                            )
                        else:
                            self.console.print(
                                f"\n  [magenta]⚙ {tool_name}[/magenta]", end=""
                            )

                    elif kind == "on_tool_end":
                        output = event.get("data", {}).get("output", "")
                        if not spinner_active:
                            out_str = str(output)[:100].replace("\n", " ")
                            self.console.print(f" [dim]→ {out_str}[/dim]")

                    elif kind == "on_chain_end":
                        # Extract token/cost data from chain output if available
                        output = event.get("data", {}).get("output", {})
                        if isinstance(output, dict):
                            if "total_tokens" in output:
                                self._total_tokens = output["total_tokens"]
                            if "total_cost" in output:
                                self._total_cost = output["total_cost"]

            except Exception as e:
                if spinner_active:
                    live.stop()
                self.console.print(f"\n  [red]Error: {e}[/red]")

        # End the response with newline
        if response_text:
            print()  # newline after streaming
            self.console.print()

        # Update token/cost tracking
        # Try to get real state from graph checkpoint
        try:
            graph_config = {"configurable": {"thread_id": self._thread_id}}
            state = self._graph.get_state(graph_config)
            if state and state.values:
                st_tokens = state.values.get("total_tokens", 0)
                st_cost = state.values.get("total_cost", 0.0)
                if st_tokens > 0:
                    self._total_tokens = st_tokens
                    self._total_cost = st_cost
        except Exception:
            pass

        # Fallback: estimate from streamed text if still zero
        if self._total_tokens == 0 and response_text:
            est_input = len(user_input) // 4 + 200  # rough prompt overhead
            est_output = len(response_text) // 4
            self._total_tokens += est_input + est_output
            self._total_cost += calculate_cost(
                self._current_model, est_input, est_output
            )

    def _handle_command(self, cmd: str) -> None:
        """Handle slash commands."""
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Check if it's a skill invocation
        builtin_cmds = {"/help", "/h", "/model", "/cost", "/clear", "/compact", "/exit", "/quit", "/q", "/skills", "/mcp"}
        skill_name = command.lstrip("/")
        skill = self._skills_registry.get(skill_name)
        if skill and command not in builtin_cmds:
            self.console.print(f"  [cyan]⚡ Running skill: {skill.name}[/cyan]")
            prompt = skill.get_prompt(args)
            self._run_agent(prompt)
            return

        if command in ("/help", "/h"):
            skills = self._skills_registry.list_skills()
            skills_text = ""
            if skills:
                skills_text = "\n\n[bold]Skills:[/bold] (use /name [args])\n"
                for s in skills:
                    aliases = f" ({', '.join(s.aliases)})" if s.aliases else ""
                    skills_text += f"  /{s.name}{aliases} - {s.description}\n"

            mcp_text = ""
            if self._mcp_manager.server_count > 0:
                mcp_text = f"\n\n[bold]MCP:[/bold] {self._mcp_manager.server_count} server(s), {self._mcp_manager.tool_count} tool(s)"

            self.console.print(Panel(
                "[bold]Commands:[/bold]\n"
                "  /help     - Show this help\n"
                "  /model    - Show or switch model (e.g. /model openai:gpt-4o)\n"
                "  /cost     - Show token usage and cost\n"
                "  /skills   - List available skills\n"
                "  /mcp      - Show MCP server status\n"
                "  /clear    - Clear screen\n"
                "  /compact  - Reset conversation\n"
                "  /exit     - Exit"
                + skills_text + mcp_text,
                title="Help",
                border_style="blue",
            ))
        elif command == "/model":
            if args:
                if ":" in args:
                    provider, model = args.split(":", 1)
                else:
                    provider = self._current_provider
                    model = args
                self._current_provider = provider
                self._current_model = model
                # Reinitialize graph with new model
                try:
                    self.config.default_provider = provider
                    self.config.default_model = model
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(self._initialize())
                    loop.close()
                    self.console.print(f"[green]Switched to {provider}:{model}[/green]")
                except Exception as e:
                    self.console.print(f"[red]Failed: {e}[/red]")
            else:
                self.console.print(
                    f"Current: [bold cyan]{self._current_provider}:{self._current_model}[/bold cyan]\n"
                    f"[dim]Usage: /model provider:model (e.g. /model openai:gpt-4o)[/dim]"
                )
        elif command == "/cost":
            self.console.print(Panel(
                f"Model:         {self._current_provider}:{self._current_model}\n"
                f"Total tokens:  {self._total_tokens:,}\n"
                f"Total cost:    {format_cost(self._total_cost)}",
                title="Usage",
                border_style="green",
            ))
        elif command == "/clear":
            self.console.clear()
        elif command == "/compact":
            import uuid
            self._thread_id = str(uuid.uuid4())
            self.console.print("[green]Conversation reset (new thread).[/green]")
        elif command == "/skills":
            skills = self._skills_registry.list_skills()
            if skills:
                lines = []
                for s in skills:
                    aliases = f" ({', '.join(s.aliases)})" if s.aliases else ""
                    lines.append(f"  /{s.name}{aliases} - {s.description}")
                self.console.print(Panel(
                    "\n".join(lines),
                    title=f"Skills ({len(skills)})",
                    border_style="cyan",
                ))
            else:
                self.console.print("[dim]No skills registered.[/dim]")
        elif command == "/mcp":
            if self._mcp_manager.server_count > 0:
                lines = [f"Connected servers: {self._mcp_manager.server_count}"]
                for name, conn in self._mcp_manager.connections.items():
                    lines.append(f"\n  [bold]{name}[/bold] ({conn.server_type})")
                    for tool in conn.tools:
                        lines.append(f"    • {tool['name']}: {tool.get('description', '')[:60]}")
                self.console.print(Panel(
                    "\n".join(lines),
                    title=f"MCP Servers ({self._mcp_manager.tool_count} tools)",
                    border_style="magenta",
                ))
            else:
                self.console.print(
                    "[dim]No MCP servers connected.[/dim]\n"
                    "[dim]Configure in ~/.tui-agent/config.json under 'mcpServers'[/dim]"
                )
        elif command in ("/exit", "/quit", "/q"):
            self.console.print("[dim]Goodbye![/dim]")
            sys.exit(0)
        else:
            self.console.print(f"[yellow]Unknown command: {command}. Try /help[/yellow]")
