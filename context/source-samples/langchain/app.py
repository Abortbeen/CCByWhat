"""Main REPL application - Claude Code style terminal interface."""

from __future__ import annotations

import asyncio
import os
import queue
import signal
import sys
import threading
import time
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from tui_agent.agent.callbacks import StreamEvent
from tui_agent.agent.core import AgentRunner
from tui_agent.config import Config
from tui_agent.mcp.client import MCPManager
from tui_agent.mcp.tool_bridge import create_mcp_tools
from tui_agent.skills.builtin import register_builtin_skills
from tui_agent.skills.registry import get_skills_registry
from tui_agent.utils.git import get_current_branch


class TUIAgentApp:
    """Claude Code style REPL terminal agent."""

    def __init__(self, config: Config, **kwargs: Any) -> None:
        self.config = config
        self.agent = AgentRunner(config)
        self.console = Console()
        self._is_processing = False
        self._session_start = time.time()
        self._tool_count = 0
        self._history: list[str] = []
        self._mcp_manager = MCPManager()
        self._skills_registry = get_skills_registry()

    def run(self) -> None:
        """Main REPL loop."""
        self.console.clear()
        self._print_welcome()

        # Initialize agent
        self.console.print("[dim]Initializing agent...[/dim]")
        try:
            self.agent.initialize()

            # Initialize MCP servers
            mcp_servers = self.config.get_mcp_servers()
            if mcp_servers:
                self.console.print(f"[dim]Connecting to {len(mcp_servers)} MCP server(s)...[/dim]")
                loop = asyncio.new_event_loop()
                connected = loop.run_until_complete(self._mcp_manager.connect_all(mcp_servers))
                loop.close()
                if connected > 0:
                    mcp_tools = create_mcp_tools(self._mcp_manager)
                    self.agent.add_tools(mcp_tools)
                    self.console.print(
                        f"[green]MCP:[/green] {connected} server(s), {self._mcp_manager.tool_count} tools"
                    )

            # Initialize skills
            register_builtin_skills()
            user_skills_dir = self.config.config_dir / "skills" if hasattr(self.config, 'config_dir') else None
            if user_skills_dir:
                from pathlib import Path
                self._skills_registry.load_from_directory(Path(str(user_skills_dir)))

            self.console.print(
                f"[green]Ready![/green] Model: [bold cyan]{self.agent.provider_name}:{self.agent.model_name}[/bold cyan]"
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

    def _print_welcome(self) -> None:
        """Print welcome banner."""
        self.console.print(
            Panel(
                "[bold]TUI Code Agent[/bold] - Multi-model coding assistant\n"
                "[dim]Type a message, /help for commands, Ctrl+C twice to exit[/dim]",
                border_style="blue",
            )
        )

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
            # Move cursor down to clean position
            sys.stdout.write(f"\x1b[{lines_below}B\n")
            sys.stdout.flush()
            raise
        # Move past pre-printed lines below
        sys.stdout.write(f"\x1b[{lines_below}E")
        sys.stdout.flush()
        return user_input

    def _build_status_lines(self) -> list[str]:
        """Build the status bar text lines (plain strings for pre-printing)."""
        branch = get_current_branch(".") or "no-git"
        elapsed = int(time.time() - self._session_start)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}m{secs:02d}s" if mins else f"{secs}s"

        usage = self.agent.callback.get_usage()
        total_tokens = usage["total_input_tokens"] + usage["total_output_tokens"]
        if total_tokens > 1000:
            token_str = f"{total_tokens/1000:.1f}k"
        else:
            token_str = str(total_tokens)

        cost = self.agent.cost_tracker.total_cost

        line1 = f"    branch:{branch}"
        line2 = f"    {self.agent.model_name} | session:{time_str} | tokens:{token_str} | ${cost:.4f} | 🔧{self._tool_count}"
        return [line1, line2]

    def _run_agent(self, user_input: str) -> None:
        """Run the agent and display streaming response."""
        self._is_processing = True
        response_text = ""

        # Start streaming in a thread
        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.agent.run_streaming(user_input))
            except Exception as e:
                self.agent.callback.queue.put(
                    StreamEvent(event_type="error", content=f"Error: {e}")
                )
                self.agent.callback.queue.put(StreamEvent(event_type="complete"))
            finally:
                loop.close()

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        # Show spinner while waiting for first token
        spinner_active = True
        first_token = True

        with Live(
            Spinner("dots", text="[bold cyan]Brewing...[/bold cyan]"),
            console=self.console,
            refresh_per_second=10,
            transient=True,
        ) as live:
            while True:
                try:
                    event = self.agent.event_queue.get(timeout=0.1)

                    if event.event_type == "token":
                        if first_token:
                            first_token = False
                            live.stop()
                            spinner_active = False
                        response_text += event.content
                        # Print token directly for streaming effect
                        print(event.content, end="", flush=True)

                    elif event.event_type == "tool_start":
                        self._tool_count += 1
                        if spinner_active:
                            live.update(
                                Spinner("dots", text=f"[bold cyan]Running {event.content}...[/bold cyan]")
                            )
                        else:
                            self.console.print(
                                f"\n  [magenta]⚙ {event.content}[/magenta]", end=""
                            )

                    elif event.event_type == "tool_end":
                        if not spinner_active:
                            # Show truncated tool output
                            output = event.content
                            if len(output) > 200:
                                output = output[:200] + "..."
                            self.console.print(f" [dim]→ {output[:100]}[/dim]")

                    elif event.event_type == "error":
                        if spinner_active:
                            live.stop()
                            spinner_active = False
                        self.console.print(f"\n  [red]{event.content}[/red]")

                    elif event.event_type == "complete":
                        break

                except queue.Empty:
                    if not thread.is_alive():
                        # Drain remaining events
                        while True:
                            try:
                                event = self.agent.event_queue.get_nowait()
                                if event.event_type == "token":
                                    response_text += event.content
                                    if spinner_active:
                                        live.stop()
                                        spinner_active = False
                                    print(event.content, end="", flush=True)
                                elif event.event_type == "complete":
                                    break
                            except queue.Empty:
                                break
                        break

        # End the response with newline
        if response_text:
            print()  # newline after streaming
            self.console.print()

        # Update token/cost tracking after streaming completes
        usage = self.agent.callback.get_usage()
        cb_input = usage["total_input_tokens"]
        cb_output = usage["total_output_tokens"]
        if cb_input > 0 or cb_output > 0:
            # Callback captured real usage — sync to cost tracker
            delta_in = cb_input - self.agent.cost_tracker.total_input_tokens
            delta_out = cb_output - self.agent.cost_tracker.total_output_tokens
            if delta_in > 0 or delta_out > 0:
                self.agent.cost_tracker.add_usage(delta_in, delta_out)
        elif response_text:
            # Fallback: estimate tokens from text (chars / 4)
            est_input = len(user_input) // 4 + 200  # rough prompt overhead
            est_output = len(response_text) // 4
            self.agent.cost_tracker.add_usage(est_input, est_output)
            self.agent.callback.total_input_tokens += est_input
            self.agent.callback.total_output_tokens += est_output

        self._is_processing = False

    def _handle_command(self, cmd: str) -> None:
        """Handle slash commands."""
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Check if it's a skill invocation
        skill_name = command.lstrip("/")
        skill = self._skills_registry.get(skill_name)
        if skill and command not in ("/help", "/h", "/model", "/cost", "/clear", "/compact", "/exit", "/quit", "/q", "/skills", "/mcp"):
            self.console.print(f"  [cyan]⚡ Running skill: {skill.name}[/cyan]")
            prompt = skill.get_prompt(args)
            self._run_agent(prompt)
            return

        if command in ("/help", "/h"):
            # Build skills list
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
                    provider = self.agent.provider_name
                    model = args
                try:
                    self.agent.switch_model(provider, model)
                    self.console.print(f"[green]Switched to {provider}:{model}[/green]")
                except Exception as e:
                    self.console.print(f"[red]Failed: {e}[/red]")
            else:
                self.console.print(
                    f"Current: [bold cyan]{self.agent.provider_name}:{self.agent.model_name}[/bold cyan]\n"
                    f"[dim]Usage: /model provider:model (e.g. /model openai:gpt-4o)[/dim]"
                )
        elif command == "/cost":
            usage = self.agent.callback.get_usage()
            self.console.print(Panel(
                f"Input tokens:  {usage['total_input_tokens']:,}\n"
                f"Output tokens: {usage['total_output_tokens']:,}\n"
                f"Total cost:    ${self.agent.cost_tracker.total_cost:.4f}",
                title="Usage",
                border_style="green",
            ))
        elif command == "/clear":
            self.console.clear()
        elif command == "/compact":
            self.agent.clear_history()
            self.console.print("[green]Conversation reset.[/green]")
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
