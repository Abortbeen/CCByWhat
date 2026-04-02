"""Configuration management for TUI Agent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_DIR = Path.home() / ".tui-agent"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "sessions.db"
DEFAULT_MEMORY_DIR = DEFAULT_CONFIG_DIR / "memory"


@dataclass
class Config:
    """Application configuration."""

    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"
    working_directory: str = field(default_factory=lambda: os.getcwd())
    max_iterations: int = 50
    max_tokens_per_response: int = 8192
    temperature: float = 0.0
    config_dir: str = field(default_factory=lambda: str(DEFAULT_CONFIG_DIR))
    db_path: str = field(default_factory=lambda: str(DEFAULT_DB_PATH))
    memory_dir: str = field(default_factory=lambda: str(DEFAULT_MEMORY_DIR))

    # Permission settings
    auto_approve_reads: bool = True
    auto_approve_writes: bool = False
    auto_approve_bash: bool = False
    allowed_bash_commands: list[str] = field(
        default_factory=lambda: [
            "git", "ls", "find", "grep", "rg", "cat", "head", "tail",
            "wc", "sort", "uniq", "diff", "echo", "pwd", "which", "env",
            "python", "pip", "node", "npm", "cargo", "go", "make",
        ]
    )

    # UI settings
    theme: str = "dark"
    show_sidebar: bool = True
    show_status_bar: bool = True
    show_token_count: bool = True
    show_cost: bool = True
    sidebar_width: int = 30

    # Provider API keys (loaded from env if not set)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Model pricing (per 1M tokens: [input, output])
    model_pricing: dict[str, list[float]] = field(default_factory=lambda: {
        "claude-sonnet-4-20250514": [3.0, 15.0],
        "claude-3-5-sonnet-20241022": [3.0, 15.0],
        "claude-3-haiku-20240307": [0.25, 1.25],
        "gpt-4o": [2.50, 10.0],
        "gpt-4o-mini": [0.15, 0.60],
        "gpt-4-turbo": [10.0, 30.0],
        "gemini-2.0-flash": [0.075, 0.30],
        "gemini-1.5-pro": [1.25, 5.0],
    })

    def __post_init__(self) -> None:
        """Load API keys from environment if not already set."""
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.google_api_key:
            self.google_api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not self.ollama_base_url:
            self.ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """Load configuration from JSON files, falling back to defaults.

        Reads from two sources (in order of priority):
        1. ~/.claude/settings.json (Claude Code compatible)
        2. ~/.tui-agent/config.json (TUI Agent specific, overrides)
        """
        _ENV_KEYS = [
            "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL",
            "OPENAI_API_KEY", "OPENAI_BASE_URL",
            "GOOGLE_API_KEY",
            "OLLAMA_BASE_URL",
        ]

        # 1. Load from ~/.claude/settings.json (Claude Code compatible)
        claude_settings = Path.home() / ".claude" / "settings.json"
        if claude_settings.exists():
            try:
                claude_data = json.loads(claude_settings.read_text(encoding="utf-8"))
                # Claude Code stores env vars under "env" key
                env_vars = claude_data.get("env", {})
                if isinstance(env_vars, dict):
                    for env_key in _ENV_KEYS:
                        if env_key in env_vars and env_vars[env_key] and not os.environ.get(env_key):
                            os.environ[env_key] = str(env_vars[env_key])
            except (json.JSONDecodeError, OSError):
                pass

        # 2. Load from ~/.tui-agent/config.json
        config_path = Path(path) if path else DEFAULT_CONFIG_FILE
        data: dict[str, Any] = {}

        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        # Set API keys and base URLs from TUI agent config into env vars
        for env_key in _ENV_KEYS:
            if env_key in data and data[env_key] and not os.environ.get(env_key):
                os.environ[env_key] = str(data[env_key])

        # Filter to only known fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def save(self, path: str | Path | None = None) -> None:
        """Save configuration to a JSON file."""
        config_path = Path(path) if path else DEFAULT_CONFIG_FILE
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            k: v for k, v in self.__dict__.items()
            if not k.endswith("_api_key")  # Never persist API keys
        }
        config_path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def get_api_key(self, provider: str) -> str:
        """Get API key for a provider."""
        key_map = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "google": self.google_api_key,
        }
        return key_map.get(provider, "")

    def get_pricing(self, model: str) -> tuple[float, float]:
        """Get pricing for a model as (input_per_1m, output_per_1m)."""
        pricing = self.model_pricing.get(model, [0.0, 0.0])
        return (pricing[0], pricing[1])

    def get_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Load MCP server configurations.

        Reads from (in order, later sources override):
        1. ~/.claude/settings.json (mcpServers - Claude Code format)
        2. ~/.tui-agent/config.json (mcpServers)
        3. ~/.tui-agent/mcp.json (dedicated MCP config)

        Returns:
            Dict mapping server name to server config.
        """
        servers: dict[str, dict[str, Any]] = {}

        # 1. Load from Claude Code settings
        claude_settings = Path.home() / ".claude" / "settings.json"
        if claude_settings.exists():
            try:
                data = json.loads(claude_settings.read_text())
                if "mcpServers" in data and isinstance(data["mcpServers"], dict):
                    servers.update(data["mcpServers"])
            except (json.JSONDecodeError, OSError):
                pass

        # 2. Load from main config
        config_path = Path(self.config_dir) / "config.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                if "mcpServers" in data and isinstance(data["mcpServers"], dict):
                    servers.update(data["mcpServers"])
            except (json.JSONDecodeError, OSError):
                pass

        # 3. Load from dedicated MCP config
        mcp_config = Path(self.config_dir) / "mcp.json"
        if mcp_config.exists():
            try:
                data = json.loads(mcp_config.read_text())
                if "mcpServers" in data and isinstance(data["mcpServers"], dict):
                    servers.update(data["mcpServers"])
                elif isinstance(data, dict) and not any(k.startswith("mcp") for k in data):
                    servers.update(data)
            except (json.JSONDecodeError, OSError):
                pass

        return servers
