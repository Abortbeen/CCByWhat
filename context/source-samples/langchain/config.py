"""Configuration management for TUI Agent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
CONFIG_DIR = Path.home() / ".tui-agent"
CONFIG_FILE = CONFIG_DIR / "config.json"
MEMORY_FILE = CONFIG_DIR / "AGENT.md"

# Default models per provider
DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "ollama": "llama3.1",
}

# Cost per 1M tokens (input, output) in USD
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-3-opus-20240229": (15.0, 75.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.0, 30.0),
    "gemini-2.0-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.0),
}


@dataclass
class Config:
    """Application configuration."""

    model: str | None = None
    provider: str | None = None
    cwd: str | None = None
    auto_approve: bool = False
    max_tokens: int = 8192
    temperature: float = 0.0
    max_conversation_tokens: int = 200_000
    allowed_commands: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Resolve defaults and load persisted config."""
        self._load_persisted()

        if self.provider is None:
            self.provider = self._detect_provider()
        if self.model is None:
            self.model = DEFAULT_MODELS.get(self.provider, DEFAULT_MODEL)
        if self.cwd is None:
            self.cwd = os.getcwd()

    def _detect_provider(self) -> str:
        """Detect the best available provider based on environment variables."""
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("GOOGLE_API_KEY"):
            return "google"
        # Ollama doesn't need an API key
        return DEFAULT_PROVIDER

    def _load_persisted(self) -> None:
        """Load persisted configuration from disk and set env vars.

        Reads from two sources (in order of priority):
        1. ~/.claude/settings.json (Claude Code compatible)
        2. ~/.tui-agent/config.json (TUI Agent specific)

        Claude Code stores env vars in settings.json under the 'env' key,
        and MCP servers under 'mcpServers'. This method supports both formats.
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
                data = json.loads(claude_settings.read_text())
                # Claude Code stores env vars under "env" key
                env_vars = data.get("env", {})
                if isinstance(env_vars, dict):
                    for env_key in _ENV_KEYS:
                        if env_key in env_vars and env_vars[env_key] and not os.environ.get(env_key):
                            os.environ[env_key] = str(env_vars[env_key])
                # Also read model from Claude Code settings
                if self.model is None and "model" in data:
                    claude_model = data["model"]
                    # Claude Code uses short names like "opus[1m]"
                    if isinstance(claude_model, str) and "[" not in claude_model:
                        self.model = claude_model
            except (json.JSONDecodeError, OSError):
                pass

        # 2. Load from ~/.tui-agent/config.json (TUI Agent specific, overrides)
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                for key, value in data.items():
                    if hasattr(self, key) and getattr(self, key) is None:
                        setattr(self, key, value)

                # Set API keys and base URLs from config into env vars
                for env_key in _ENV_KEYS:
                    if env_key in data and data[env_key] and not os.environ.get(env_key):
                        os.environ[env_key] = str(data[env_key])
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        """Persist current configuration to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "auto_approve": self.auto_approve,
            "allowed_commands": self.allowed_commands,
            "blocked_paths": self.blocked_paths,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))

    @property
    def working_directory(self) -> Path:
        """Return the resolved working directory."""
        return Path(self.cwd or os.getcwd()).resolve()

    def get_cost_per_million(self) -> tuple[float, float]:
        """Return (input_cost, output_cost) per 1M tokens for the current model."""
        return MODEL_COSTS.get(self.model or "", (0.0, 0.0))

    def get_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Load MCP server configurations.

        Reads from (in order, later sources override):
        1. ~/.claude/settings.json (mcpServers key - Claude Code format)
        2. ~/.tui-agent/config.json (mcpServers key)
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
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                if "mcpServers" in data and isinstance(data["mcpServers"], dict):
                    servers.update(data["mcpServers"])
            except (json.JSONDecodeError, OSError):
                pass

        # 3. Load from dedicated MCP config
        mcp_config = CONFIG_DIR / "mcp.json"
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

    @property
    def config_dir(self) -> Path:
        """Return the config directory path."""
        return CONFIG_DIR
