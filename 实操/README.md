# 实操目录

请在课程根目录完成环境安装，然后按顺序运行：

```bash
python 实操/tool_calling.py
python 实操/state_graph.py
python 实操/multi_agent.py
python 实操/eval_pipeline.py
python 实操/durable_execution.py
python 实操/trace_eval.py
python 实操/mcp_compatibility.py
python 实操/test_course_examples.py -v
```

默认使用本地 Mock，不调用外部模型。真实模型与 LangSmith 配置见根目录 `.env.example`。

七个实验各自只突出一个知识点；新增实验分别覆盖可恢复执行、trace 级评估和 MCP 多轮工具结果。综合项目由学员按主教材末尾的验收标准完成。
