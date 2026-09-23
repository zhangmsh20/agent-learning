# Agent Learning 课程地图

## 目标

完成课程后，学习者应能把一个多步任务拆成可检查的 Agent 系统：有明确的状态、工具契约、权限边界、失败恢复、trace 和回归评估，而不是只展示一次成功对话。

## 学习路径

| 阶段 | 主问题 | 实操 | 完成证据 |
| --- | --- | --- | --- |
| 1. 判断 | 何时用 Workflow、单 Agent 或多 Agent？ | 阅读第 1—3 章 | 能写出任务边界和失败模式 |
| 2. 闭环 | 上下文、RAG、工具和结构化输出如何连接？ | `tool_calling.py`、`state_graph.py` | 工具失败时不编造，状态契约可验证 |
| 3. 协作 | 多 Agent 的收益是否覆盖协调成本？ | `multi_agent.py` | 能比较调用次数、延迟和路由复杂度 |
| 4. 运行时 | 长任务如何暂停、恢复、取消和幂等重试？ | `durable_execution.py`、`mcp_compatibility.py` | checkpoint 可恢复，副作用不重复 |
| 5. 评估 | 如何证明过程安全且线上可回归？ | `eval_pipeline.py`、`trace_eval.py` | bad case 被发现，trace 规则可审计 |

## 课程边界

所有示例默认离线 Mock，不要求 API key。模型名称、价格、SDK 参数和 MCP 版本只在带日期的“平台观察”中出现，不应被当作稳定机制。
