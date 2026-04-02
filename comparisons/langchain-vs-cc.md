# TUI-Agent-LangChain vs Claude Code 特性对比

## 项目信息
- **框架**: LangChain v1.2 (create_agent API)
- **代码量**: ~5,609 行 Python (59 files)
- **仓库**: https://github.com/Abortbeen/tui-agent-langchain

## 特性对比

| 特性 | Claude Code | TUI-Agent-LangChain | 差距 |
|------|------------|---------------------|------|
| **TUI 引擎** | React Ink 全屏 | Rich REPL (Spinner + Status Bar) | CC 更丰富 |
| **Agent 循环** | 自研 ReAct | create_agent → compiled StateGraph | LC 简洁但黑盒 |
| **Skill 系统** | 35+ bundled | 10 内置 + 用户自定义 (.md) | CC 更多, LC 可扩展 |
| **工具数量** | 29+ 内置 | 8 内置 + MCP 桥接 | CC 更多, LC 可通过 MCP 扩展 |
| **模型支持** | Anthropic 原生 | 4 Provider (Anthropic/OpenAI/Google/Ollama) | ✅ LC 更多 |
| **流式输出** | 原生 streaming | BaseCallbackHandler + queue.Queue | ✅ 稳定可靠 |
| **权限系统** | Auto/Plan/Manual | auto_approve 开关 | CC 远领先 |
| **MCP 协议** | 原生完整支持 | ✅ stdio/SSE + 自动 BaseTool 桥接 | ✅ 基本对等 |
| **Session 管理** | 保存/恢复/compact | MemorySaver checkpoint + clear | CC 更完善 |
| **上下文注入** | 自动 CLAUDE.md | AGENT.md persistent memory | 基本对等 |
| **Cost 追踪** | 实时显示 | ✅ 状态栏实时显示 (估算 + 回调) | ✅ 对等 |
| **CC 配置兼容** | — | ✅ 读取 ~/.claude/settings.json | LC 独有 |
| **Anthropic 内容块** | 原生处理 | ✅ _to_str() 处理 list/dict/str | ✅ 已适配 |

## 框架原生提供 vs 自建

| 能力 | 框架提供 | 自建 |
|------|---------|------|
| LLM 多模型 | ✅ langchain-anthropic/openai/google | — |
| create_agent | ✅ 一行创建 ReAct Agent | — |
| BaseTool 标准化 | ✅ Pydantic schema | — |
| 流式回调 | ✅ BaseCallbackHandler | — |
| Checkpoint | ✅ MemorySaver | — |
| TUI/REPL | — | ✅ Rich REPL (~300 行) |
| MCP 集成 | — | ✅ MCP SDK + tool bridge (~400 行) |
| Skills 系统 | — | ✅ registry + builtin (~500 行) |
| Cost 追踪 | — | ✅ CostTracker (~100 行) |
| CC 配置兼容 | — | ✅ settings.json loader (~50 行) |

**自建比例: ~30%**

## CC-Bench 评分: 3.45 / 5.00

**结论**: LangChain v1.2 的 create_agent 大幅降低了搭建成本。
一行代码得到完整的 ReAct Agent, 再加上 MCP SDK 集成就能扩展工具生态。
最大缺点是 Agent 循环是黑盒, 无法自定义节点和边。
适合快速原型, 不适合需要精细控制的生产场景。
