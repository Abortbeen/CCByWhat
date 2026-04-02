# Evaluation Context Guide

## 评估环境说明

这个目录包含了 Claude Code 进行评估时的完整上下文环境。

## 目录结构

```
context/
├── CONTEXT-GUIDE.md              # 本文件
├── claude-code-config/           # Claude Code 自身的配置
│   ├── settings.json             # ~/.claude/settings.json (API key 已脱敏)
│   └── CLAUDE.md                 # 全局 CLAUDE.md 项目指令
├── project-configs/              # 被评估项目的配置
│   └── tui-agent-config.json     # ~/.tui-agent/config.json
├── reference-docs/               # 参考文档
│   ├── agentscope-internal-summary.md  # AgentScope 项目内部总结 (痛点分析)
│   ├── agentscope-code-README.md       # AgentScope-Code 项目 README
│   ├── tui-agent-langchain-README.md   # LangChain 版 README
│   └── tui-agent-langgraph-README.md   # LangGraph 版 README
└── source-samples/               # 关键源码样本
    ├── langchain/                # LangChain 版核心文件
    │   ├── app.py                # Rich REPL 主循环
    │   ├── agent_core.py         # create_agent + streaming
    │   ├── mcp_client.py         # MCP 客户端
    │   ├── skills_registry.py    # Skills 注册系统
    │   └── config.py             # 配置 (兼容 ~/.claude/settings.json)
    └── langgraph/                # LangGraph 版核心文件
        ├── app.py                # Rich REPL 主循环
        ├── graph_agent.py        # StateGraph 定义
        ├── graph_nodes.py        # think/act/observe/respond 节点
        ├── graph_state.py        # AgentState TypedDict
        └── config.py             # 配置 (兼容 ~/.claude/settings.json)
```

## 评估环境

| 项 | 值 |
|----|-----|
| 评估模型 | claude-opus-4-6 (via Claude Code) |
| API 代理 | https://api.zstack.ai |
| 操作系统 | Linux (Ubuntu) |
| Python | 3.12 (miniforge3 conda) |
| 工作目录 | /root/zql/zql/zql/ |
| Claude Code 版本 | 最新 (2026-04) |

## 评估流程

1. **分析阶段** — 阅读 claude-code-main 源码 (512k 行 TS)，理解 CC 架构
2. **构建阶段** — 分别用 LangChain v1.2 和 LangGraph 构建 TUI Agent
3. **调试阶段** — 修复 Textual 8.x 兼容性、Anthropic 内容块格式、流式回调等 bug
4. **重写阶段** — 从 Textual TUI 重写为 Rich REPL (Claude Code 风格)
5. **集成阶段** — 添加 MCP 客户端、Skills 系统、CC 配置兼容
6. **评估阶段** — 对比三个框架 (AgentScope/LangChain/LangGraph) 在 CC 复刻上的表现
7. **文档阶段** — 编写 CC-Bench 评价框架和排名

## 关键发现

评估过程中的关键发现记录在 `reference-docs/agentscope-internal-summary.md`
和主 `README.md` 的"思考"章节中。核心结论：

> Agent 循环本身只占 Claude Code 代码量的 ~15%。剩下的 85% 是框架层无法提供的
> "最后一公里"产品工程——TUI、权限、MCP、Skills、Hooks、上下文自动化。
