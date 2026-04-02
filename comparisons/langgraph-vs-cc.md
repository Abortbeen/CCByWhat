# TUI-Agent-LangGraph vs Claude Code 特性对比

## 项目信息
- **框架**: LangGraph (StateGraph)
- **代码量**: ~5,168 行 Python (61 files)
- **仓库**: https://github.com/Abortbeen/tui-agent-langgraph

## 特性对比

| 特性 | Claude Code | TUI-Agent-LangGraph | 差距 |
|------|------------|---------------------|------|
| **TUI 引擎** | React Ink 全屏 | Rich REPL (Spinner + Status Bar) | CC 更丰富 |
| **Agent 循环** | 自研 | ✅ StateGraph: think→permissions→act→observe→respond | ✅ 最接近 CC |
| **Skill 系统** | 35+ bundled | 10 内置 + 用户自定义 (.md) | CC 更多, LG 可扩展 |
| **工具数量** | 29+ 内置 | 8 内置 + MCP 桥接 | CC 更多, LG 可扩展 |
| **模型支持** | Anthropic 原生 | 4 Provider (Anthropic/OpenAI/Google/Ollama) | ✅ LG 更多 |
| **流式输出** | 原生 streaming | ✅ astream_events v2 (细粒度) | ✅ LG 更细粒度 |
| **权限系统** | Auto/Plan/Manual | check_permissions 节点 + interrupt | LG 架构上最接近 CC |
| **MCP 协议** | 原生完整支持 | ✅ stdio/SSE + 自动 BaseTool 桥接 | ✅ 基本对等 |
| **Session 管理** | 保存/恢复/compact | ✅ MemorySaver + resume via thread_id | ✅ 架构对等 |
| **上下文注入** | 自动 CLAUDE.md | AGENT.md + ConversationManager | 基本对等 |
| **Cost 追踪** | 实时显示 | ✅ 状态栏实时 (graph state + 估算) | ✅ 对等 |
| **CC 配置兼容** | — | ✅ 读取 ~/.claude/settings.json | LG 独有 |
| **可观测性** | 内置 tracing | ✅ 每个节点转换可追踪 | ✅ LG 接近 CC |
| **循环安全** | 内置 | ✅ MAX_ITERATIONS = 50 | ✅ 对等 |
| **Human-in-the-loop** | 原生 | ✅ interrupt() 机制 | ✅ 最接近 CC |

## StateGraph 拓扑 (最接近 CC 架构)

```
START → think → should_use_tools?
  → YES → check_permissions → approved?
      → YES → act → observe → continue?
          → YES → think (loop)
          → NO → respond
      → NO → wait_for_permission → act
  → NO → respond → END
```

## 框架原生提供 vs 自建

| 能力 | 框架提供 | 自建 |
|------|---------|------|
| StateGraph 定义 | ✅ 节点、边、条件路由 | — |
| Checkpointer | ✅ MemorySaver / SQLite / Postgres | — |
| astream_events | ✅ v2 细粒度流式 | — |
| interrupt | ✅ human-in-the-loop 暂停 | — |
| Provider Registry | — | ✅ 多 Provider 注册 (~200 行) |
| Tool Registry | — | ✅ 工具发现和注册 (~140 行) |
| TUI/REPL | — | ✅ Rich REPL (~300 行) |
| MCP 集成 | — | ✅ MCP SDK + tool bridge (~400 行) |
| Skills 系统 | — | ✅ registry + builtin (~500 行) |
| Graph Nodes | — | ✅ think/act/observe/respond (~200 行) |
| Token 计数 | — | ✅ tiktoken + 估算 (~80 行) |
| Cost 计算 | — | ✅ MODEL_PRICING + calculate_cost (~100 行) |

**自建比例: ~25%**

## CC-Bench 评分: 3.60 / 5.00 (🥇 最高)

**结论**: LangGraph 在架构思想上最接近 Claude Code。
StateGraph 允许定义与 CC 一致的 think→act→observe 循环,
interrupt 机制天然支持权限暂停, Checkpointer 原生解决 session 持久化。
astream_events v2 提供的细粒度流式事件是三个框架中最优的。
唯一不足是搭建复杂度略高于 LangChain (需定义 State/Nodes/Edges),
但换来了完全可控、可观测、可恢复的生产级 Agent 循环。
