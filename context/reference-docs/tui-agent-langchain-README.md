# TUI Code Agent (LangChain)

An open-source, multi-model, extensible terminal coding agent built on [LangChain](https://github.com/langchain-ai/langchain). Feature-complete to match the capabilities of Claude Code, with a minimal REPL-style terminal interface powered by [Rich](https://github.com/Textualize/rich).

## Features

- **Multi-model support** - Switch between Anthropic, OpenAI, Google, and Ollama models on the fly
- **Claude Code style REPL** - Minimal terminal interface with spinner animation, streaming output, and status bar
- **Full coding toolkit** - 8 built-in tools: bash, file read/write/edit, glob, grep, web fetch, web search
- **Real-time streaming** - Token-by-token output as the agent thinks and responds
- **Tool call visualization** - See tool names and outputs inline as they execute
- **Slash commands** - Quick actions: `/model`, `/cost`, `/clear`, `/compact`, `/exit`
- **Cost tracking** - Real-time token usage and cost estimation in the status bar
- **Persistent memory** - Project notes via AGENT.md that survive between sessions
- **Context management** - Compact or clear conversation history to manage context windows
- **LangChain v1.2+ create_agent API** - Uses the modern compiled StateGraph agent under the hood

## Demo

```
╭──────────────────────────────────────────────────╮
│ TUI Code Agent - Multi-model coding assistant    │
│ Type a message, /help for commands, Ctrl+C ×2    │
╰──────────────────────────────────────────────────╯
  branch:master
  anthropic:claude-opus-4-6 | session:24s | tokens:1.2k | $0.0042 | tools:3
  ────────────────────────────────────────
  ❯ Read src/main.py and explain what it does
  ────────────────────────────────────────
  ⠹ Brewing...
  ⚙ file_read → src/main.py (42 lines)
  
  This file defines the main entry point for the application...
```

## Installation

### From source (recommended)

```bash
git clone https://github.com/your-org/tui-code-agent-langchain.git
cd tui-code-agent-langchain

# Create a conda environment
conda create -n tui-agent-langchain python=3.12 -y
conda activate tui-agent-langchain

pip install -e .
```

### With pip

```bash
pip install tui-code-agent-langchain
```

## Quick Start

1. **Configure your API key** in `~/.tui-agent/config.json`:

```json
{
  "provider": "anthropic",
  "model": "claude-opus-4-6",
  "ANTHROPIC_API_KEY": "sk-ant-...",
  "ANTHROPIC_BASE_URL": "https://api.anthropic.com"
}
```

Or set environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AI..."
```

2. **Launch the agent:**

```bash
tui-agent
# or
python -m tui_agent
```

3. **Specify a model:**

```bash
tui-agent --provider openai --model gpt-4o
tui-agent --provider anthropic --model claude-sonnet-4-20250514
tui-agent --provider ollama --model llama3.1
```

## CLI Options

| Flag | Description |
|------|-------------|
| `--model, -m` | Model name (e.g., `gpt-4o`, `claude-opus-4-6`) |
| `--provider, -p` | Provider: `anthropic`, `openai`, `google`, `ollama` |
| `--cwd` | Working directory (defaults to current) |
| `--no-permissions` | Auto-approve all tool calls |
| `--version, -v` | Show version |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/model [provider:model]` | View or switch the active LLM |
| `/cost` | Show token usage and estimated cost |
| `/clear` | Clear the screen |
| `/compact` | Reset conversation (new thread) |
| `/exit` | Exit the agent |

## Tools

| Tool | Description |
|------|-------------|
| `bash` | Execute shell commands with timeout and working directory |
| `file_read` | Read file contents with line numbers, offset, and limit |
| `file_write` | Create or overwrite files, auto-creating directories |
| `file_edit` | Precise string replacement in files |
| `glob` | Find files by glob pattern (e.g., `**/*.py`) |
| `grep` | Regex content search (uses ripgrep when available) |
| `web_fetch` | Fetch and extract text from URLs |
| `web_search` | Search the web via DuckDuckGo |

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Rich REPL Interface                 │
│  ┌──────────────────────────────────────────┐   │
│  │  Status Bar (branch, model, tokens, $)   │   │
│  │  ❯ User Input                            │   │
│  │  ⠹ Spinner / Streaming Output            │   │
│  │  ⚙ Tool Calls + Results                  │   │
│  └──────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────┘
                     │
             ┌───────▼───────┐
             │  AgentRunner   │
             │  (LangChain    │
             │  create_agent) │
             └───────┬───────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
 ┌───────▼──┐ ┌──────▼───┐ ┌────▼─────┐
 │ LLM      │ │  Tools   │ │ Memory   │
 │ Registry │ │ (8 tools)│ │ (AGENT.md│
 └──────────┘ └──────────┘ └──────────┘
```

### Core Components

- **`app.py`** - Rich-based REPL with spinner, streaming, status bar
- **`agent/core.py`** - LangChain v1.2 `create_agent()` returning a compiled StateGraph
- **`agent/callbacks.py`** - Sync `BaseCallbackHandler` with thread-safe `queue.Queue`
- **`agent/prompts.py`** - System prompt with coding assistant guidelines
- **`llm/registry.py`** - Multi-provider LLM factory (Anthropic, OpenAI, Google, Ollama)
- **`tools/registry.py`** - Tool creation and configuration
- **`memory/persistent.py`** - AGENT.md file loading for project context

## Supported Models

### Anthropic
- claude-opus-4-6, claude-sonnet-4-20250514, claude-3-5-sonnet-20241022, claude-3-haiku-20240307

### OpenAI
- gpt-4o, gpt-4o-mini, gpt-4-turbo

### Google
- gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash

### Ollama (local)
- Any locally installed model (llama3.1, codellama, deepseek-coder-v2, etc.)

## Project Structure

```
src/tui_agent/
├── __main__.py          # CLI entry point
├── app.py               # Rich REPL application (Claude Code style)
├── config.py            # Configuration (JSON + env vars)
├── agent/
│   ├── core.py          # AgentRunner (create_agent + streaming)
│   ├── callbacks.py     # TUIStreamingCallback (queue-based)
│   └── prompts.py       # System prompt builder
├── llm/
│   ├── registry.py      # create_llm() factory
│   ├── anthropic.py     # Claude provider
│   ├── openai.py        # GPT provider
│   ├── google.py        # Gemini provider
│   └── ollama.py        # Local Ollama provider
├── tools/
│   ├── registry.py      # create_all_tools()
│   ├── bash.py          # Shell execution
│   ├── file_read.py     # File reading
│   ├── file_write.py    # File creation
│   ├── file_edit.py     # File editing
│   ├── glob_tool.py     # File search
│   ├── grep.py          # Content search
│   ├── web_fetch.py     # URL fetching
│   └── web_search.py    # Web search
├── memory/
│   └── persistent.py    # AGENT.md project memory
├── ui/                  # Legacy Textual widgets (unused)
└── utils/
    ├── cost.py          # Cost tracking
    └── git.py           # Git helpers
```

## Development

```bash
git clone https://github.com/your-org/tui-code-agent-langchain.git
cd tui-code-agent-langchain
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
ruff format src/

# Type check
mypy src/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Run the linter and type checker
5. Submit a pull request

### Adding a New Tool

1. Create a new file in `src/tui_agent/tools/`
2. Define a Pydantic input schema
3. Extend `BaseTool` with `_run` and `_arun` methods
4. Register it in `tools/registry.py`

### Adding a New LLM Provider

1. Create a new file in `src/tui_agent/llm/`
2. Implement the provider with `get_chat_model()` method
3. Register it in `llm/registry.py`

## License

MIT License - see [LICENSE](LICENSE) for details.
