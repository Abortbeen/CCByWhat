# AgentScope-Code vs Claude Code 特性对比

## 项目信息
- **框架**: AgentScope
- **代码量**: ~8,049 行 Python (58 files)
- **仓库**: https://github.com/Abortbeen/Agentscope-code

## 特性对比

| 特性 | Claude Code | AgentScope-Code | 差距 |
|------|------------|-----------------|------|
| **TUI 引擎** | React Ink 全屏组件化 | prompt_toolkit + Rich (自建) | CC 领先一代 |
| **Agent 定义** | .md + frontmatter 热加载 | 19 个 Python Agent 定义 (自建 loader) | AS 数量多但加载方式落后 |
| **Skill 系统** | 35+ bundled, 支持 hot-reload | 35 个 (移植自 OMC, 自建 registry) | 功能对等, 框架无原生支持 |
| **工具数量** | 29+ 内置 | 29 个 (含 Team/Task/Agent) | ✅ 对等 |
| **模型支持** | Anthropic 原生 | 5 Provider (OpenAI/Anthropic/DashScope/Gemini/Ollama) | ✅ AS 更多 |
| **流式输出** | 原生 streaming | 回调式 streaming | 基本对等 |
| **权限系统** | Auto/Plan/Manual + allow/deny | 自建 3 模式 + allow/deny | 功能对等, 完全自建 |
| **MCP 协议** | 原生完整支持 | ❌ 无 | CC 有, AS 无 |
| **A2A 协议** | 无 | ✅ Agent-to-Agent 通信 | AS 独有 |
| **Session 管理** | 保存/恢复/compact | 自建 session 管理 | 功能对等, 完全自建 |
| **上下文注入** | 自动 CLAUDE.md + git info | 自建 SystemPromptBuilder | 功能对等, 完全自建 |
| **Cost 追踪** | 实时 input/output/cost | 自建 TokenTracker | 功能对等, 框架无支持 |
| **Hook 引擎** | Pre/Post ToolUse 等 | 自建 hook engine | 功能对等, 完全自建 |
| **Studio 可观测** | 无 (CLI only) | ✅ AgentScope Studio Web UI | AS 独有优势 |
| **Tab 补全** | 原生 | ✅ 自建 slash command 补全 | 对等 |
| **多 Agent 协同** | Agent/Team/Task | ✅ MsgHub + Pipeline | 架构对等 |

## 自建模块清单 (框架未提供)

| 模块 | 代码量(估) | 说明 |
|------|-----------|------|
| CLI REPL | ~800 行 | prompt_toolkit Session + KeyBindings |
| TUI 渲染 | ~600 行 | Rich Spinner/Panel/Markdown |
| Permission | ~400 行 | 3 模式权限中间件 |
| Agent Loader | ~300 行 | .md frontmatter 解析 |
| Skill System | ~500 行 | Registry + Loader + InvokeSkill |
| Project Memory | ~300 行 | CLAUDE.md 逐级扫描 |
| Cost Tracker | ~200 行 | Token/Cost 累积 |
| Hook Engine | ~300 行 | Pre/Post 生命周期钩子 |
| Session Manager | ~400 行 | 保存/恢复/列表 |
| **合计** | **~3,800 行** | **约占总代码 47%** |

## CC-Bench 评分: 2.25 / 5.00

**结论**: AgentScope 的核心价值在于 ReActAgent + 多模型适配 + Studio 可观测。
但 CLI Agent 场景下, 框架只覆盖了约 40% 的需求, 剩余 60% 需要大量胶水代码。
搭建痛感最强, 但最终产出的功能也最丰富(19 Agent + 35 Skill + A2A)。
