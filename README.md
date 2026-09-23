# Agent Learning：从行动闭环到可恢复、可审计的 Agent Runtime

> 当前版本：教材 v2.2 · 课程仓库 v0.1.0 · 校准日期 2026-09-23  
> 适合对象：具备基础 Python 阅读能力，希望从机制到工程实践学习 Agent 的学习者

这不是一个“接上模型就算完成”的 Demo 集合，而是一套可以 clone、离线运行、自动验收和继续扩展的课程仓库。课程强调：每次行动都要有状态、契约、权限、失败路径、恢复策略和评估证据。

## 5 分钟开始

```bash
git clone <课程仓库地址>
cd agent-learning
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
python -m unittest discover -s 实操 -p 'test_*.py' -v
```

默认测试不调用外部模型、不产生费用，也不需要 API key。仓库公开地址确认后，再把上面的 `<课程仓库地址>` 替换为固定 GitHub URL。

这套课程不从某个框架的 API 开始，而是沿着一条稳定的问题链展开：

1. 什么任务值得使用 Agent？
2. 模型每一轮看到了什么？
3. 外部知识和工具怎样进入决策闭环？
4. 多步任务如何保存状态、记忆和人工审批点？
5. 什么时候使用工作流、单 Agent 或多 Agent？
6. 怎样用评估、观测和安全机制证明系统可以上线？
7. 长任务如何暂停、恢复、取消，并在运行时变化后保持可审计？

## 建议学习路线

### 第一阶段：建立判断框架

阅读主教材第 1—3 章。目标是能够区分 Chatbot、Workflow 和 Agent，并能解释 token、上下文和结构化输出对系统设计的影响。

### 第二阶段：构建单 Agent 能力

阅读第 4—7 章，依次完成：

```bash
python 实操/tool_calling.py
python 实操/state_graph.py
```

目标是掌握 RAG、工具调用、状态图和记忆的边界，不把它们混成一个概念。

### 第三阶段：走向系统工程

阅读第 8—10 章，依次完成：

```bash
python 实操/multi_agent.py
python 实操/eval_pipeline.py
```

目标是能够比较单 Agent 与多 Agent 的协调成本，建立 Eval 集，并设计权限、审批、日志和回归测试。

### 第四阶段：综合项目

完成主教材末尾的客服 Agent 综合项目。先使用 Mock 数据通过验收，再选择一个真实模型接入；不要反过来。

### 第五阶段：2026-09 Runtime 实验

```bash
python 实操/durable_execution.py
python 实操/trace_eval.py
python 实操/mcp_compatibility.py
```

目标是掌握 checkpoint / resume、幂等工具、trace 级评估和 MCP 2026-07-28 的多轮工具结果。

## 环境安装

建议使用 Python 3.11 或更高版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

默认实验全部使用本地 Mock，不需要 API key，也不会产生模型费用。

如需真实调用：

```bash
cp .env.example .env
set -a
source .env
set +a
```

不要把 `.env`、API key、真实用户数据或生产日志提交到课程目录。

## 一键验收

安装依赖后运行：

```bash
python 实操/test_course_examples.py -v
```

验收覆盖工具调用、工具失败、状态路由、多 Agent 开销和离线 Eval。任何正式发布都应先通过这组测试。

也可以运行完整发现器：

```bash
python -m unittest discover -s 实操 -p 'test_*.py' -v
python -m compileall -q 实操
```

## 正式材料

- `教材/AI_Agent_完整学习文档_2026_v2_教学版.md`：学员主教材
- `教材/AI_Agent_教师用题库_2026_v2.md`：课堂、作业和项目验收题
- `教材/教材逻辑与改造说明_2026-07.md`：课程设计、内容边界和 2026-09 更新策略
- `教材/平台观察_2026-09.md`：近期模型、运行时、MCP 和弃用信息
- `实操/tool_calling.py`：工具 schema、工具结果和失败兜底
- `实操/state_graph.py`：LangGraph 状态与条件路由
- `实操/multi_agent.py`：Orchestrator-Subagent 的离线结构实验
- `实操/eval_pipeline.py`：本地 Eval 与可选 LangSmith 上传
- `实操/durable_execution.py`：checkpoint、人工审批、恢复、取消和幂等
- `实操/trace_eval.py`：过程 trace、成本/延迟和行为级评分
- `实操/mcp_compatibility.py`：MCP 2026-07-28 工具结果与多轮输入示例

`归档/` 中的 HTML、阶段更新稿、评审记录和历史版本是设计过程资料，不是学员必读入口。

- `docs/syllabus.md`：课程地图与每阶段完成证据
- `docs/release-checklist.md`：发布、CI 和 Knowabit 展示前检查清单
- `docs/github-publishing.md`：创建远程仓库、验证 CI 和发布 Release 的步骤
- `CHANGELOG.md`：版本变化

## 内容更新原则

课程把内容分成三层：

- 稳定机制：Agent 闭环、上下文选择、工具契约、状态、评估和权限。
- 可运行实验：默认离线、可重复、有自动测试。
- 平台观察：模型名称、价格、SDK 参数和预览能力，只记录校准日期并链接官方资料。

平台观察至少每月快速复核、每季度系统复核；稳定机制只有在概念或教学证据发生变化时才重写。

## 与 Knowabit 的关系

课程仓库负责教材、实例、测试和 Release；Knowabit 负责公开的 Project 介绍、学习路线和入口。网站不承载 API key、课程运行时数据或生产日志。当前本地预览入口为 `/projects/agent-learning`；GitHub 公开仓库地址在远程仓库创建并验证后再写入页面。
