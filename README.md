# Claude Code Replication Benchmark (CC-Bench)

## 用 AI 编程 Agent 的复刻来度量 Agent 框架的工程能力

> 作者思考：Claude Code 是目前最成熟的终端 AI 编程助手，拥有完整的工具链、权限系统、MCP 协议、
> Skills 生态、上下文管理、多模型支持和会话持久化。**"能否在一个 Agent 框架上快速复刻 Claude Code
> 的核心体验"本身就是检验该框架工程完备度的最佳 benchmark。** 这不是跑分，而是一个端到端的
> 系统工程挑战——它同时考验框架的 LLM 抽象层、工具系统、流式输出、状态管理、终端交互和可扩展性。

---

## 📁 仓库结构

```
CCByWhat/
├── README.md                              # CC-Bench 完整评测框架（本文件）
├── comparisons/                           # 各框架 vs CC 详细对比
│   ├── agentscope-vs-cc.md                #   AgentScope vs Claude Code
│   ├── langchain-vs-cc.md                 #   LangChain vs Claude Code
│   └── langgraph-vs-cc.md                 #   LangGraph vs Claude Code
├── sessions/                              # 完整 Claude Code 对话记录
│   ├── SESSION-GUIDE.md                   #   会话说明
│   ├── session-main-8894f1cb.jsonl        #   主会话 (4MB) — 构建两个 TUI Agent
│   ├── session-prev-6d3e77a1.jsonl        #   前序会话 (1.2MB) — AgentScope 项目
│   └── session-today-23e15e3d.jsonl       #   辅助会话 — 环境配置
├── context/                               # 评估时 CC 的完整上下文环境
│   ├── CONTEXT-GUIDE.md                   #   上下文说明
│   ├── claude-code-config/                #   Claude Code 自身配置
│   │   ├── settings.json                  #     ~/.claude/settings.json (key 已脱敏)
│   │   └── CLAUDE.md                      #     全局 CLAUDE.md
│   ├── project-configs/                   #   被评估项目的配置
│   │   └── tui-agent-config.json          #     ~/.tui-agent/config.json (key 已脱敏)
│   ├── reference-docs/                    #   参考文档
│   │   ├── agentscope-internal-summary.md #     AgentScope 内部痛点分析
│   │   ├── agentscope-code-README.md      #     AgentScope-Code 项目 README
│   │   ├── tui-agent-langchain-README.md  #     LangChain 版 README
│   │   └── tui-agent-langgraph-README.md  #     LangGraph 版 README
│   └── source-samples/                    #   关键源码样本
│       ├── langchain/                     #     LangChain 版: app.py, agent_core.py, mcp_client.py, skills_registry.py, config.py
│       └── langgraph/                     #     LangGraph 版: app.py, graph_agent.py, graph_nodes.py, graph_state.py, config.py
└── .gitignore
```

---

## 一、立意：为什么 CC 复刻是一个好 Benchmark

### 1.1 传统 Agent Benchmark 的局限

| Benchmark | 测什么 | 缺什么 |
|-----------|--------|--------|
| SWE-bench | 代码修复准确率 | 不测框架，测模型 |
| HumanEval | 函数生成 | 不测系统工程 |
| GAIA | 多步推理 | 不测 TUI/权限/扩展性 |
| AgentBench | 环境交互 | 不测产品完整度 |

### 1.2 CC-Bench 的独特价值

Claude Code 的复刻要求框架同时具备：

1. **LLM 抽象** — 多模型、多 Provider、流式输出
2. **工具系统** — 定义、注册、权限控制、结果回传
3. **Agent 循环** — ReAct / StateGraph / 自定义 loop
4. **终端交互** — REPL、Spinner、Markdown 渲染、状态栏
5. **协议扩展** — MCP 服务器连接、工具桥接
6. **上下文管理** — 项目记忆、会话持久化、上下文压缩
7. **生态适配** — Skills、Hooks、Plugin 加载
8. **产品细节** — 成本追踪、Git 集成、权限提示

**这些维度在任何单一 benchmark 中都不会同时出现。CC 复刻是一个"全栈 Agent 系统工程"的综合考试。**

---

## 二、评价体系

### 2.1 评价维度（8 维度）

| 维度 | 权重 | 含义 |
|------|------|------|
| **D1. LLM 抽象层** | 15% | 多模型切换、流式输出、Token 追踪 |
| **D2. 工具系统** | 15% | 工具数量、定义方式、异步支持、结果格式 |
| **D3. Agent 循环** | 15% | 推理-行动循环的灵活性、可调试性、安全边界 |
| **D4. 终端交互** | 10% | TUI 质量、Spinner、Markdown、状态栏 |
| **D5. 权限与安全** | 10% | 工具级权限、用户确认、敏感操作检测 |
| **D6. 协议扩展** | 10% | MCP 支持、外部工具桥接、Plugin 加载 |
| **D7. 上下文管理** | 10% | 项目记忆、会话保存/恢复、上下文压缩 |
| **D8. 框架胶水成本** | 15% | 框架提供多少 vs 需要自建多少（越少自建越好）|

### 2.2 评价指标（每维度 5 分制）

| 分数 | 含义 |
|------|------|
| 5 | 框架原生支持，开箱即用 |
| 4 | 框架有 80% 支持，少量适配 |
| 3 | 框架有基础支持，需要中等胶水代码 |
| 2 | 框架仅有原语，大量自建 |
| 1 | 框架无支持，完全自建 |

---

## 三、四个项目对比总览

### 3.1 基本信息

| 指标 | Claude Code (原版) | Agentscope-Code | TUI-Agent-LangChain | TUI-Agent-LangGraph |
|------|-------------------|-----------------|---------------------|---------------------|
| **框架** | 自研 (TypeScript) | AgentScope | LangChain v1.2 | LangGraph |
| **语言** | TypeScript/React | Python | Python | Python |
| **代码量** | ~512k 行 TS | ~8k 行 Py (58 files) | ~5.6k 行 Py (59 files) | ~5.2k 行 Py (61 files) |
| **Agent 数** | 多种内置 | 19 个专业 Agent | 1 (create_agent) | 1 (StateGraph) |
| **Skill 数** | 35+ bundled | 35 (移植 OMC) | 10 内置 | 10 内置 |
| **工具数** | 29+ | 29 | 8 + MCP 桥接 | 8 + MCP 桥接 |
| **模型支持** | Anthropic 原生 | 5 Provider | 4 Provider | 4 Provider |
| **TUI** | React Ink 全屏 | prompt_toolkit + Rich | Rich REPL | Rich REPL |
| **MCP** | 原生完整支持 | 无 | ✅ stdio/SSE | ✅ stdio/SSE |
| **A2A** | 无 | ✅ | 无 | 无 |
| **权限** | Auto/Plan/Manual | 自建 3 模式 | 基础 auto_approve | 分层 auto/approval |
| **会话持久化** | 完整 | 自建 session | 内存 checkpoint | MemorySaver checkpoint |
| **CC 配置兼容** | — | 否 | ✅ ~/.claude/settings.json | ✅ ~/.claude/settings.json |

### 3.2 八维度评分

| 维度 | CC (参考) | AgentScope | LangChain v1.2 | LangGraph |
|------|-----------|------------|----------------|-----------|
| D1. LLM 抽象层 | 5 | 4 | 4 | 4 |
| D2. 工具系统 | 5 | 3 | 4 | 4 |
| D3. Agent 循环 | 5 | 3 | 4 | 5 |
| D4. 终端交互 | 5 | 2 | 3 | 3 |
| D5. 权限与安全 | 5 | 1 | 2 | 2 |
| D6. 协议扩展 | 5 | 1 | 4 | 4 |
| D7. 上下文管理 | 5 | 1 | 3 | 4 |
| D8. 框架胶水成本 | 5 | 2 | 3 | 3 |
| **加权总分** | **5.00** | **2.25** | **3.45** | **3.60** |

---

## 四、各项目详细分析

### 4.1 Agentscope-Code（基于 AgentScope 框架）

#### 优势
- **多 Agent 架构最丰富** — 19 个专业 Agent，这是其他项目不具备的
- **Skill 移植最完整** — 35 个 Skill，直接从 oh-my-claudecode 移植
- **工具数量最多** — 29 个工具，包含 Team、Task、Agent Spawn
- **A2A 协议** — 唯一支持 Agent-to-Agent 通信的项目
- **Studio 可观测** — 可接入 AgentScope Studio Web UI

#### 痛点（引用 internal-summary.md）
- **Studio Hooks 无法禁用** — 自动注册导致大量 WARNING
- **无 CLI/TUI 层抽象** — 完全自建终端交互（prompt_toolkit + Rich）
- **Anthropic Formatter Bug** — tool_result 缺少 type 字段
- **无权限层** — 完全自建 PermissionChecker
- **无项目上下文注入** — 完全自建 SystemPromptBuilder
- **无 MCP 支持** — AgentScope 没有 MCP 协议适配
- **无 Session 管理** — 完全自建 session 保存/恢复

**核心结论**：AgentScope 提供了 ReActAgent + Toolkit + 多模型适配的底座，
但从"框架能力"到"可交付产品"之间有**大量胶水代码**（8 个独立模块需自建）。
搭建成本最高（19,315 行 → 其中约 60% 是胶水代码）。

#### 评分理由
- D1 = 4：多模型适配好，但 Anthropic formatter 有 bug
- D2 = 3：Toolkit 注册方便，但无权限钩子、无 MCP
- D3 = 3：ReActAgent 可用，但不够灵活（无 StateGraph 级别的自定义）
- D4 = 2：完全没有 CLI 层，全部自建
- D5 = 1：框架层零权限支持
- D6 = 1：无 MCP、无 Plugin 加载机制
- D7 = 1：无上下文、无 session 管理
- D8 = 2：胶水代码占比约 60%

---

### 4.2 TUI-Agent-LangChain（基于 LangChain v1.2）

#### 优势
- **create_agent API 简洁** — 一行代码创建完整的 ReAct Agent
- **流式回调成熟** — BaseCallbackHandler + queue.Queue 稳定可靠
- **MCP 完整集成** — stdio/SSE 协议，自动工具桥接到 BaseTool
- **Claude Code 配置兼容** — 读取 ~/.claude/settings.json
- **开发速度快** — LangChain 的 create_agent 封装了 LangGraph

#### 痛点
- **create_agent 是黑盒** — 内部是 compiled StateGraph，但无法自定义节点/边
- **Token 追踪不可靠** — 流式模式下 on_llm_end 不一定提供 token_usage
- **无 Agent 定义文件格式** — 不支持 .md + frontmatter 定义
- **权限系统基础** — 只有 auto_approve 开关，无分级
- **Agent 循环不可见** — 内部 think→act→observe 循环无法观测

#### 评分理由
- D1 = 4：create_llm 多 Provider 好用，streaming 回调完善
- D2 = 4：BaseTool 标准化好，MCP 桥接顺畅
- D3 = 4：create_agent 开箱即用，但不可自定义
- D4 = 3：Rich REPL 可用，但无 prompt_toolkit 高级功能
- D5 = 2：只有 auto_approve，无分级权限
- D6 = 4：MCP 支持完整，Skills 系统自建
- D7 = 3：MemorySaver checkpoint，persistent memory via AGENT.md
- D8 = 3：约 30% 胶水代码

---

### 4.3 TUI-Agent-LangGraph（基于 LangGraph）

#### 优势
- **StateGraph 完全可控** — think→check_permissions→act→observe→respond 每个节点可自定义
- **Checkpointing 原生** — MemorySaver/SQLite 开箱即用，支持 session resume
- **astream_events 流式** — v2 API 提供细粒度事件（token/tool_start/tool_end/chain_end）
- **可观测性最好** — 每个节点转换都可追踪
- **interrupt 机制** — 原生支持 human-in-the-loop 权限暂停
- **MCP 完整集成** — 同 LangChain 版
- **Claude Code 配置兼容** — 读取 ~/.claude/settings.json
- **循环安全** — MAX_ITERATIONS 防止无限循环

#### 痛点
- **搭建复杂度稍高** — 需要定义 State、Nodes、Edges、Conditional routing
- **Token 追踪需自建** — 节点内的 token 计数是手动实现
- **无 Agent 定义文件格式** — 同 LangChain 版
- **TUI 层仍需自建** — LangGraph 不提供终端交互

#### 评分理由
- D1 = 4：通过 Provider Registry 多模型好用
- D2 = 4：BaseTool + bind_tools + MCP 桥接
- D3 = 5：StateGraph 是目前最灵活的 Agent 循环定义方式
- D4 = 3：Rich REPL 可用
- D5 = 2：有 check_permissions 节点 + interrupt 机制（比 LangChain 好）
- D6 = 4：MCP 支持完整
- D7 = 4：Checkpointer 原生，session resume，上下文压缩
- D8 = 3：约 25% 胶水代码

---

## 五、CC-Bench 框架排名

### 5.1 总排名

| 排名 | 框架 | 加权总分 | 核心优势 | 核心短板 |
|------|------|---------|---------|---------|
| 🥇 1 | **LangGraph** | **3.60** | StateGraph 可控、Checkpoint 原生、astream_events | TUI 需自建 |
| 🥈 2 | **LangChain v1.2** | **3.45** | create_agent 简洁、回调成熟、开发速度快 | Agent 循环是黑盒 |
| 🥉 3 | **AgentScope** | **2.25** | 多 Agent 定义、Studio 可观测 | 胶水代码量大、无 CLI/权限/MCP |

### 5.2 分维度最佳

| 维度 | 最佳框架 | 说明 |
|------|---------|------|
| D1. LLM 抽象层 | 三者持平 (4) | 都有成熟的多 Provider 支持 |
| D2. 工具系统 | LangChain / LangGraph (4) | BaseTool 标准化 + MCP 桥接 |
| D3. Agent 循环 | **LangGraph (5)** | StateGraph 是唯一可完全自定义的 |
| D4. 终端交互 | LangChain / LangGraph (3) | 都需要 Rich 自建，但比 AS 好 |
| D5. 权限与安全 | LangGraph (2+) | interrupt 机制最接近 CC |
| D6. 协议扩展 | LangChain / LangGraph (4) | MCP SDK 集成成熟 |
| D7. 上下文管理 | **LangGraph (4)** | Checkpointer 原生支持 |
| D8. 框架胶水成本 | LangChain / LangGraph (3) | 自建比例最低 |

### 5.3 框架选型建议

| 场景 | 推荐框架 | 理由 |
|------|---------|------|
| 快速原型 | LangChain v1.2 | create_agent 一行起步 |
| 生产级 Agent | LangGraph | 可控、可观测、可恢复 |
| 多 Agent 协同 | AgentScope | 原生 MsgHub + Pipeline |
| 最快复刻 CC | LangGraph | 最接近 CC 的架构思想 |

---

## 六、思考：框架的天花板在哪里

### 6.1 所有框架共同缺失的能力

对比 Claude Code（512k 行 TypeScript），**所有 Python Agent 框架都缺失**：

1. **全屏 TUI 引擎** — CC 用 React Ink 实现组件化全屏 TUI，Python 生态没有对等方案
2. **原生权限系统** — 无框架内置 Auto/Plan/Manual 三模式
3. **Skill 作为一等公民** — 无框架将 Skill（prompt 模板）与 Tool（代码执行）区分
4. **Hook 引擎** — 无框架提供 PreToolUse/PostToolUse/PreReply 等生命周期钩子
5. **上下文自动化** — 无框架自动收集 CLAUDE.md + git info + project structure
6. **成本追踪内置** — 无框架在 Agent 层面自动累积 token/cost

### 6.2 CC 架构的核心洞察

Claude Code 不是一个"框架上搭的 Agent"，而是一个**围绕编程场景深度优化的产品**。
它的 512k 行代码中：

- ~30% 是 TUI/UX（React Ink 组件、键绑定、Vim 模式、语音输入）
- ~25% 是 工具实现（29+ tools，每个都有深度的错误处理和边界检查）
- ~20% 是 基础设施（MCP、OAuth、Plugin、Settings、Hooks）
- ~15% 是 Agent 逻辑（推理循环、compact、memory、session）
- ~10% 是 API/协议层（Anthropic SDK、streaming、retry、rate limit）

**关键洞察**：Agent 循环本身只占 15%——这正是框架能覆盖的部分。
剩下的 85% 是框架层无法提供的"最后一公里"产品工程。

### 6.3 对 Agent 框架发展的建议

| 建议 | 详情 |
|------|------|
| **内置 CLI/TUI 层** | 提供 `framework.cli.REPL` 基类，让 CLI Agent 一行启动 |
| **权限作为一等概念** | Tool 调用前的 pre-check hook，per-agent 的 allow/deny 列表 |
| **MCP 原生支持** | 框架层提供 MCP client，自动将 MCP tools 注册为 Agent tools |
| **Skill ≠ Tool** | 区分"代码执行"（Tool）和"prompt 注入"（Skill），两者是不同抽象层 |
| **上下文自动化** | 自动收集项目 README、配置文件、git 信息作为 Agent 上下文 |
| **Cost tracking 内置** | Model 层自动累积 token usage，Agent 层暴露 `.cost` 属性 |

---

## 七、项目列表

| 项目 | 框架 | 仓库 |
|------|------|------|
| Agentscope-Code | AgentScope | https://github.com/Abortbeen/Agentscope-code |
| TUI-Agent-LangChain | LangChain v1.2 | https://github.com/Abortbeen/tui-agent-langchain |
| TUI-Agent-LangGraph | LangGraph | https://github.com/Abortbeen/tui-agent-langgraph |
| Claude Code (参考) | 自研 | 闭源 (Anthropic) |

---

## 附录 A：评分方法论

每个维度的评分基于以下标准：

**D1. LLM 抽象层 (15%)**
- 5分：框架原生支持 5+ Provider、流式输出、自动 token 追踪
- 4分：支持多 Provider、流式输出，token 需少量适配
- 3分：支持主流 Provider，流式需适配
- 2分：仅支持单一 API 格式
- 1分：需自建 LLM 调用层

**D2. 工具系统 (15%)**
- 5分：标准工具定义、Schema 推断、权限钩子、MCP 桥接
- 4分：标准工具定义、Schema 推断、MCP 需适配
- 3分：工具注册机制有，但无权限/MCP
- 2分：仅有基础函数注册
- 1分：需自建工具系统

**D3. Agent 循环 (15%)**
- 5分：完全可自定义的 Graph/State 循环，带观测点
- 4分：高层 API 可用但不可自定义内部
- 3分：ReAct 可用，但灵活性有限
- 2分：仅有基础 prompt→response 循环
- 1分：需自建 Agent 循环

**D4. 终端交互 (10%)**
- 5分：框架提供 CLI/TUI 模块
- 4分：提供渲染工具集
- 3分：需用第三方库（Rich）自建 REPL
- 2分：需从零自建所有终端交互
- 1分：无任何终端支持

**D5. 权限与安全 (10%)**
- 5分：Auto/Plan/Manual 三模式 + allow/deny + 敏感检测
- 4分：框架有权限钩子，需配置
- 3分：有基础拦截机制
- 2分：仅有开关级（auto_approve）
- 1分：无任何权限支持

**D6. 协议扩展 (10%)**
- 5分：MCP 原生 + Plugin 系统 + 热加载
- 4分：MCP 可集成 + 基础 Plugin
- 3分：可扩展但需大量适配
- 2分：仅有 Tool 注册
- 1分：封闭系统

**D7. 上下文管理 (10%)**
- 5分：自动收集项目上下文 + session 持久化 + compact
- 4分：Checkpoint 原生 + 手动上下文注入
- 3分：有基础 memory + 手动 context
- 2分：仅有消息历史
- 1分：无状态管理

**D8. 框架胶水成本 (15%)**
- 5分：框架覆盖 90%+ 需求
- 4分：框架覆盖 70%+
- 3分：框架覆盖 50%+，自建约 30%
- 2分：自建 50%+
- 1分：自建 70%+，框架仅提供原语
