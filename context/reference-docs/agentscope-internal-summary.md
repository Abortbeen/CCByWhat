# Agentscope-Code 项目内部总结

> 内部文档，不公开。用于团队消化和向 AgentScope 团队提 PRD。

---

## 一、项目概述

基于 AgentScope 框架搭建了一个 Claude Code 风格的终端 AI 编程 Agent。
目标：验证 AgentScope 作为通用 Agent 框架，能否快速复刻 Claude Code 的核心体验。

**结论：能搭，但很痛。** AgentScope 提供了 ReActAgent + Toolkit + 多模型适配的底座，
但从"框架能力"到"可交付产品"之间有大量胶水代码，暴露了 AS 在 CLI Agent 场景下的设计短板。

---

## 二、搭建成果

| 维度 | 数据 |
|------|------|
| 代码量 | 114 files, 19,315 行 Python |
| Agent 定义 | 19 个专业 Agent（从 oh-my-claudecode 移植） |
| Skill 定义 | 35 个 Skill（bundled + OMC） |
| 工具数 | 29 个 Tool（Bash, File, Glob, Grep, Web, Git, Agent, Team, Task, Plan...） |
| 模型支持 | 5 个 Provider（OpenAI, Anthropic, DashScope, Gemini, Ollama） |
| TUI 特性 | Spinner, 分隔线, 多行状态栏, Shift+Tab 模式切换, Tab 补全 |
| 协议支持 | A2A (Agent-to-Agent), AgentScope Studio |

---

## 三、搭建过程中遇到的核心痛点

### 痛点 1：Studio Hooks 无法干净禁用（严重）

**现象**：AgentScope 初始化时自动注册 `_studio_hooks`，即使不用 Studio 也会尝试 HTTP 转发，
失败后打印大量 WARNING 日志，且用标准 logging 手段无法抑制（logger 名为 `"as"` 而非 `"agentscope"`）。

**我们的解法**：
1. 强制 `logging.getLogger("as").setLevel(CRITICAL)`
2. Monkey-patch `_studio_hooks.py` 源码，将函数体改为 `return`
3. 每次 Agent 创建后重新清理 class-level hooks

**AS 应该做的**：
- Studio hooks 应该只在 `studio.enabled=True` 时注册
- 提供 `agentscope.init(studio=False)` 的显式关闭方式
- Logger 名称应该与包名一致（`agentscope.*` 而非 `as`）

---

### 痛点 2：没有 CLI/TUI 层的抽象（严重）

**现象**：AS 只有 Studio（Web UI）和 Gradio 作为交互层，完全没有终端交互的支持。
要做一个 CLI Agent 必须自己搭：
- prompt_toolkit 的 PromptSession + KeyBindings + Completer + Style
- Rich 的 Markdown/Panel/Spinner 渲染
- 自定义 Spinner 动画（AS 的 `console.status` 会被其他输出打断）
- 底部状态栏（bottom_toolbar）的布局管理
- ANSI 转义序列的手动处理

**CC 对比**：Claude Code 用 React Ink 实现了完整的全屏 TUI，
组件化地管理 Messages、PromptInput、Divider、Spinner、StatusBar。

**AS 应该做的**：
- 提供 `agentscope.cli` 模块，内置 REPL 循环 + 终端渲染
- 或者至少提供 `TerminalRenderer` 接口，让框架层管理输出格式

---

### 痛点 3：Anthropic Formatter 有 Bug（中等）

**现象**：`AnthropicChatFormatter` 生成的 `tool_result` content block 缺少 `type` 字段，
Anthropic API（尤其是代理/中转服务）严格要求 `{"type": "text", "text": "..."}`。

**我们的解法**：Monkey-patch `formatter._format`，遍历所有 tool_result 补上 `type` 字段。

**AS 应该做的**：
- `AnthropicChatFormatter` 应确保 tool_result 的 content block 始终包含 `type` 字段
- 增加 Anthropic API 兼容性测试

---

### 痛点 4：没有 Permission 层（中等）

**现象**：AS 的 Tool 调用没有任何权限控制。Agent 可以执行任意 Bash 命令、读写任意文件。
对于 coding agent 这是不可接受的安全风险。

**CC 对比**：Claude Code 有完整的权限系统：
- `allowedTools` / `disallowedTools` per agent
- Auto / Plan / Manual 三种模式
- 敏感文件检测 (.env, *.pem, credentials)
- 用户确认机制

**我们的解法**：自建 `PermissionChecker` 中间件 + 三种模式 + allow/deny 规则。

**AS 应该做的**：
- Tool 调用应支持 pre-check hook，允许框架层拦截
- 提供 `ToolPermission` 配置，per-agent 的 allowed/denied tools
- `ReActAgent` 应内置 `permission_mode` 参数

---

### 痛点 5：没有 Project Memory / Context 注入（中等）

**现象**：AS 没有"项目上下文"的概念。每次创建 Agent 都要手动拼 system prompt，
没有自动扫描 CLAUDE.md / AGENT.md / .agent/ 目录的机制。

**CC 对比**：Claude Code 自动加载：
- `~/.claude/CLAUDE.md`（全局）
- 项目目录逐级向上查找 `CLAUDE.md`
- `.claude/settings.json` 项目配置

**我们的解法**：自建 `SystemPromptBuilder.load_project_memory()` 逐级扫描。

**AS 应该做的**：
- 提供 `agentscope.context` 模块，自动收集项目上下文
- `ReActAgent` 支持 `context_files` 参数

---

### 痛点 6：Agent Definition 加载不标准（低）

**现象**：AS 没有从 `.md` 文件加载 Agent 定义的标准方式。
oh-my-claudecode 和 Claude Code 都用 YAML frontmatter + Markdown body 定义 Agent，
但 AS 完全不支持这种模式。

**我们的解法**：自建 `AgentDefinitionLoader`，支持 frontmatter 解析 + 多目录搜索。

**AS 应该做的**：
- 提供标准的 Agent 定义文件格式
- `agentscope.agent.from_definition(path)` 工厂方法

---

### 痛点 7：没有 Skill/Command 系统（低）

**现象**：AS 只有 Tool（函数级），没有 Skill（prompt 级）的概念。
Claude Code 的 Skill 是高层指令模板，包含触发条件、步骤、约束，
本质上是"可复用的 system prompt 片段"。

**我们的解法**：自建 `SkillRegistry` + `SkillLoader` + `InvokeSkill` tool。

**AS 应该做的**：
- 提供 `Skill` 抽象，区分 Tool（代码执行）和 Skill（prompt 注入）
- 支持 hot-reload 和优先级机制

---

### 痛点 8：Token/Cost 追踪不在框架层（低）

**现象**：AS 的 model 调用返回值中有 usage 信息，但框架层不追踪、不累积。
要做 token 计数和费用估算必须自己写。

**CC 对比**：Claude Code 实时显示 input/output tokens、session 总量、费用。

**我们的解法**：自建 `TokenTracker` dataclass。

**AS 应该做的**：
- `ModelBase` 层自动累积 token usage
- 提供 `agent.token_usage` 属性

---

## 四、CC vs AS 设计理念差异

| 设计维度 | Claude Code | AgentScope | 差距 |
|----------|-------------|------------|------|
| **交互层** | 全屏 TUI (React Ink)，组件化 | Studio (Web) + API，无 CLI | CC 领先一代 |
| **Agent 定义** | .md 文件 + frontmatter，热加载 | Python 代码，静态 | CC 更灵活 |
| **权限模型** | Auto/Plan/Manual + allow/deny | 无 | CC 有，AS 无 |
| **上下文管理** | 自动收集 CLAUDE.md + git info | 手动拼 system prompt | CC 自动化 |
| **工具生态** | 29+ 内置，MCP 协议扩展 | Toolkit 注册，无标准扩展协议 | CC 更开放 |
| **多 Agent** | Agent/Team/Task 三层协调 | MsgHub + Pipeline | 架构相当 |
| **可观测性** | 内置 cost tracking + context bar | Studio tracing（可选） | CC 更原生 |
| **Skill 系统** | Skill = prompt 模板 + 触发条件 | 无对应概念 | CC 有，AS 无 |
| **Session** | 自动保存/恢复/compact | 无内置 session 管理 | CC 有，AS 无 |

---

## 五、给 AgentScope 团队的 PRD 建议

### P0（建议优先做）

1. **CLI Agent 快速搭建能力**
   - 提供 `agentscope.cli.REPL` 基类
   - 内置 prompt_toolkit 集成（补全、样式、键绑定）
   - 内置 Spinner + Markdown 渲染
   - 一行代码启动：`REPL(agent).run()`

2. **Studio Hooks 按需注册**
   - 只在 `studio.enabled=True` 时注册 hooks
   - 提供显式 `agentscope.init(studio=False)` 
   - 统一 logger 命名为 `agentscope.*`

3. **Tool 权限层**
   - `ReActAgent(allowed_tools=[...], denied_tools=[...])`
   - Pre-tool-use hook 支持拦截/确认
   - 内置敏感操作检测

### P1（建议中期做）

4. **Project Context 自动注入**
   - 自动扫描 `AGENT.md` / `CLAUDE.md` / `.agent/` 
   - `ReActAgent(context_dir=".agent/")` 
   - Git info 自动收集

5. **Token Usage 追踪**
   - `ModelBase` 层自动累积
   - `agent.usage` → `{input_tokens, output_tokens, cost}`
   - 支持 per-turn 和 session 级统计

6. **Agent Definition 文件格式**
   - 标准化 `.md` + YAML frontmatter 格式
   - `AgentBase.from_file("agents/architect.md")`
   - 支持 `disallowedTools`、`model` 覆盖

### P2（建议长期做）

7. **Skill 系统**
   - `Skill` 抽象 = prompt 模板 + 触发条件 + 允许的工具
   - 支持 bundled / user / project 三级
   - 热加载 + 优先级

8. **Session 管理**
   - 对话保存/恢复/compact
   - 自动 memory compression
   - Session 列表和搜索

9. **A2A 协议原生支持**
   - Agent Card 自动生成
   - 标准 REST API 暴露 agent 能力
   - 跨框架 agent 互操作

---

## 六、复用价值

本项目的以下模块可以直接提取为独立包或贡献给 AS：

| 模块 | 文件 | 价值 |
|------|------|------|
| CLI REPL | `cli/repl.py` + `cli/tui.py` | 通用 CLI Agent 交互层 |
| Permission | `permissions/` | 通用 Tool 权限中间件 |
| Agent Loader | `agent/agent_loader.py` | .md Agent 定义加载器 |
| Skill System | `skills/` | 通用 Skill 注册/加载/调用 |
| Project Memory | `memory/` + `agent/system_prompt.py` | CLAUDE.md 式项目上下文 |
| Cost Tracker | `observability/cost_display.py` | 多模型费用追踪 |
| Hook Engine | `hooks/engine.py` | Pre/Post hook 系统 |

---

## 七、结论

AgentScope 的核心优势在于 **多模型适配 + ReActAgent + Toolkit 注册**，
这三块节省了大量底层工作。但从"框架"到"产品"的最后一公里，
Claude Code 的设计理念（CLI-first、权限内置、上下文自动化、Skill 生态）
明显领先 AgentScope 至少一个版本迭代。

**建议**：将本项目的 8 个模块整理为 PR 提交给 AgentScope，
重点推动 P0 的三项（CLI REPL、Studio hooks 修复、Tool 权限层），
这三项做完后 AS 搭 CLI Agent 的成本可以从"两周"降到"两小时"。
