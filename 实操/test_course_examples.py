"""课程示例的离线验收测试。

默认不调用任何外部模型或观测平台。
"""

import contextlib
import io
import unittest

import eval_pipeline
import multi_agent
import tool_calling
import durable_execution
import mcp_compatibility
import trace_eval


class ToolCallingTests(unittest.TestCase):
    def setUp(self):
        self.agent = tool_calling.CustomerServiceAgent(use_mock=True)

    def run_silently(self, message: str) -> str:
        with contextlib.redirect_stdout(io.StringIO()):
            return self.agent.run(message)

    def test_missing_order_id_is_requested(self):
        reply = self.run_silently("我的快递怎么还没到？")
        self.assertIn("订单号", reply)

    def test_shipping_result_is_returned(self):
        reply = self.run_silently("订单 A1001 的物流到哪里了？")
        self.assertIn("上海转运中心", reply)

    def test_ticket_result_does_not_use_shipping_fields(self):
        reply = self.run_silently("订单 A1003 延迟太久了，帮我建个工单")
        self.assertIn("人工工单", reply)
        self.assertIn("已创建", reply)

    def test_unknown_order_is_not_fabricated(self):
        reply = self.run_silently("帮我查一下订单 Z9999 的状态")
        self.assertIn("未找到订单", reply)


class StateGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import state_graph
        except ModuleNotFoundError as exc:
            if exc.name == "langgraph":
                raise unittest.SkipTest("需要先安装 requirements.txt") from exc
            raise
        cls.module = state_graph
        cls.app = state_graph.build_graph()

    def invoke(self, message: str):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.app.invoke(self.module.make_initial_state(message))

    def test_not_found_result_is_explained(self):
        state = self.invoke("查一下订单 Z9999")
        self.assertIn("未找到订单", state["reply"])

    def test_refund_does_not_claim_unexecuted_ticket(self):
        state = self.invoke("我要退款，订单 A1002")
        self.assertTrue(state["needs_human"])
        self.assertNotIn("已创建", state["reply"])


class MultiAgentTests(unittest.TestCase):
    def test_multi_agent_has_coordination_overhead(self):
        multi_agent.multi_agent_usage = multi_agent.TokenUsage()
        multi_agent.single_agent_usage = multi_agent.TokenUsage()
        with contextlib.redirect_stdout(io.StringIO()):
            multi_agent.Orchestrator().run("订单 A1001 的物流状态")
            multi_agent.SingleAgent().run("订单 A1001 的物流状态")
        self.assertGreater(
            multi_agent.multi_agent_usage.call_count,
            multi_agent.single_agent_usage.call_count,
        )

    def test_parallel_demo_returns_separate_results(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = multi_agent.run_parallel_demo("订单 A1001 的物流和退货政策")
        self.assertEqual("parallel_subagents", result["mode"])
        self.assertEqual(2, len(result["results"]))


class DurableExecutionTests(unittest.TestCase):
    def test_resume_after_approval_is_idempotent(self):
        agent = durable_execution.DurableAgent()
        agent.start("task-test", "U001", "物流延迟")
        persisted = agent.store.export()
        restored = durable_execution.DurableAgent(
            durable_execution.CheckpointStore.import_store(persisted), agent.tool
        )
        restored.approve("task-test", True)
        first = restored.resume("task-test")
        second = restored.resume("task-test", force_retry=True)
        self.assertEqual("completed", first.status)
        self.assertEqual(first.result["ticket_id"], second.result["ticket_id"])
        self.assertTrue(second.result["replayed"])
        self.assertEqual(1, len(restored.tool.created))


class RuntimeProtocolTests(unittest.TestCase):
    def test_mcp_input_required_then_complete(self):
        first = mcp_compatibility.call_tool({"order_id": "A1001"})
        self.assertEqual("input_required", first["resultType"])
        second = mcp_compatibility.call_tool({"order_id": "A1001", "region": "华东"})
        self.assertEqual("complete", second["resultType"])

    def test_trace_grader_catches_unexecuted_refund(self):
        result = trace_eval.grade_trace(trace_eval.BAD_TRACE)
        self.assertFalse(result["passed"])
        self.assertTrue(any("已退款" in failure for failure in result["failures"]))


class EvalPipelineTests(unittest.TestCase):
    def test_expected_demo_regressions_are_found(self):
        results = eval_pipeline.EvalRunner().run(eval_pipeline.EVAL_DATASET)
        failed_ids = {result.case_id for result in results if not result.passed}
        self.assertEqual({"error_01", "error_02"}, failed_ids)


if __name__ == "__main__":
    unittest.main()
