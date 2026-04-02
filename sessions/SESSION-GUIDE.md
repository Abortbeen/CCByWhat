# Session Logs Guide

## 会话说明

这些是使用 Claude Code (claude-opus-4-6) 构建整个项目的完整对话记录。

### 会话文件

| 文件 | 日期 | 大小 | 内容 |
|------|------|------|------|
| `session-main-8894f1cb.jsonl` | 2026-04-02 | ~4MB | **主会话** — 构建 tui-agent-langchain/langgraph、修 bug、重写 REPL UI、集成 MCP/Skills、CC 配置兼容、创建 Benchmark 文档 |
| `session-prev-6d3e77a1.jsonl` | 2026-04-01 | ~1.2MB | 前序会话 — AgentScope-Code 项目构建和调试 |
| `session-today-23e15e3d.jsonl` | 2026-04-02 | ~63KB | 辅助会话 — 环境配置和测试 |

### 格式

每个 `.jsonl` 文件是 Claude Code 的原始对话日志，每行一个 JSON 对象，包含：
- `type`: "human" / "assistant" / "tool_use" / "tool_result"
- `content`: 消息内容
- `timestamp`: 时间戳

### 如何阅读

```bash
# 查看人类消息
cat session-main-8894f1cb.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get('type') == 'human':
        print(msg.get('message', {}).get('content', '')[:200])
        print('---')
"
```

### 隐私说明

- API Key 已从配置文件中脱敏 (`sk-REDACTED`)
- Session 日志包含完整的代码上下文和工具调用，可能包含文件路径等系统信息
