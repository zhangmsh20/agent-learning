# AI Agent 完整学习教材 2026 v2 说明

> 稳定机制复核：2026-09-23  
> 平台资料校准：2026-09-23  
> 对应教材文件：[AI_Agent_完整学习文档_2026_v2_教学版.md](AI_Agent_完整学习文档_2026_v2_教学版.md)

## 编写原则

很多 Agent 学习材料会很快变成工具清单：今天讲 LangGraph，明天讲 MCP，后天讲某个新 SDK。这样的材料看起来完整，但学生学完以后常常只记住名词，不知道一个 Agent 到底为什么会动、什么时候会错、怎么证明它可靠。

本教材采用更接近教科书的结构：

1. 先解释概念产生的原因，再给术语。
2. 先讲机制，再讲框架。
3. 先用可验证的例子建立直觉，再给抽象总结。
4. 练习题必须可以回答，参考答案必须能检查。
5. 对模型名称、价格、上下文窗口、SDK 参数等高变动信息，不写成永久结论。

教材使用一个贯穿案例：电商客服 Agent。它从一个只能回答政策问题的小助手，逐步扩展为能检索知识库、调用订单工具、记录用户偏好、触发人工审批并接受评估的系统。

## 资料来源与更新方式

Agent 领域变化很快，尤其是模型名称、上下文窗口、价格、API 参数和 SDK 用法。教材中的稳定概念以讲解为主，容易变化的内容请以官方文档为准。

| 主题 | 建议核对的官方资料 |
|---|---|
| OpenAI 模型与 API | [OpenAI 最新模型指南](https://developers.openai.com/api/docs/guides/latest-model)、[Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses)、[Agents](https://developers.openai.com/api/docs/guides/agents)、[Background](https://developers.openai.com/api/docs/guides/background)、[Compaction](https://developers.openai.com/api/docs/guides/compaction) |
| Anthropic Agent 方法 | [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)、[Claude 工具调用](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)、[Claude 模型概览](https://docs.anthropic.com/en/docs/about-claude/models/overview) |
| Google Gemini 模型 | [Gemini API Models](https://ai.google.dev/gemini-api/docs/models) |
| MCP 协议 | [MCP 官方介绍](https://modelcontextprotocol.io/docs/getting-started/intro)、[MCP 2026-07-28 Changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)、[MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) |
| LangGraph | [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)、[Memory](https://docs.langchain.com/oss/python/langgraph/memory)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/interrupts) |
| RAG | [LangChain RAG 教程](https://docs.langchain.com/oss/python/langchain/rag) |
| 评估与观测 | [OpenAI Evals](https://platform.openai.com/docs/guides/evals)、[OpenAI Agent Evals](https://developers.openai.com/api/docs/guides/agent-evals)、[OpenAI Graders](https://platform.openai.com/docs/guides/graders)、[LangSmith Evaluation](https://docs.smith.langchain.com/evaluation)、[LangSmith Observability](https://docs.smith.langchain.com/observability)、[Langfuse Docs](https://langfuse.com/docs) |
| 安全 | [OpenAI Agents Guardrails](https://openai.github.io/openai-agents-python/guardrails/)、[OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/)、[NIST Generative AI Profile](https://www.nist.gov/itl/ai-risk-management-framework/generative-artificial-intelligence-profile) |

## 教材修订记录

- v2 教材版：从课程大纲式结构改为“概念讲解、案例解析、本章小结、练习题与参考答案”的教材结构。
- v2 扩充版：移除正文中的说明性内容，扩充 Agent 基础、Token、上下文、RAG、工具调用和状态之间的知识链路。
- v2 后半部分重写版：基于最新官方资料重写第 6-9 章，扩充记忆系统、任务推进模式、Agent 评估与 trace、安全护栏、成本和产品化内容。
- v2 可运行预览版（2026-07-30）：保留十章主线，新增统一学习入口、依赖配置和自动验收；修复工具调用与状态图示例；纠正 MCP `inputSchema` 历史描述；把已弃用的 OpenAI Evals Platform 路径替换为本地 Eval harness；补充托管式 Agent、后台执行、compaction、sandbox、动态工具和短期凭据。
- v2.1 可运行更新版（2026-09-23）：新增可恢复执行、checkpoint / resume、幂等工具、trace 级评估、MCP 2026-07-28 多轮结果、并行 Subagent 和 Computer/Browser Use 安全；更新 OpenAI Agents API、Anthropic Opus 5.5、Gemini 3.8 与 SDK 迁移提示。
- v2.2 主教材复评版（2026-09-23）：补充结构化输出校验、RAG 权限/时效/版本、工具治理字段、重试/取消/补偿、记忆治理、Judge 校准、线上漂移监控，并提高综合项目验收门槛。
