"""
第8章配套代码：最小 Orchestrator-Subagent 模式

对应教材知识点：
  - Orchestrator 如何分发任务给 Subagent
  - Subagent 的结果如何汇总回 Orchestrator
  - 什么时候这个模式比单 Agent 更贵（token 统计对比）
  - Handoff 机制：Orchestrator 如何决定把任务交给哪个 Subagent

运行方式：
  python 实操/multi_agent.py

Mock 说明：
  LLM API 调用被 MockLLMRouter / MockLLMWorker 替代。
  两个类分别模拟 Orchestrator 和 Subagent 的行为。
  Token 统计是为了比较结构开销的字符级估算，不代表任何厂商账单。

图结构：
  用户消息
    ↓
  Orchestrator（决定路由 + 汇总结果）
    ↓ handoff
  ┌──────────────────┐
  │                  │
  PolicyAgent    ShippingAgent    （两个专职 Subagent）
  │                  │
  └────────┬─────────┘
           ↓ 结果返回 Orchestrator
  Orchestrator（生成最终回复）
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal


# ── Token 计数器 ──────────────────────────────────────────────────────────────
# 记录每次模拟调用的字符级 token 估算，用于比较结构开销。
# 真实项目必须读取 API response.usage，不能用这里的数字做预算。

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    call_count: int = 0

    def add(self, input_t: int, output_t: int):
        self.input_tokens += input_t
        self.output_tokens += output_t
        self.call_count += 1

    def summary(self) -> str:
        return (f"调用 {self.call_count} 次 | "
                f"输入 {self.input_tokens} token | "
                f"输出 {self.output_tokens} token")


# 全局 token 统计（多 Agent 方案 vs 单 Agent 方案）
multi_agent_usage = TokenUsage()
single_agent_usage = TokenUsage()


# ── Mock LLM ──────────────────────────────────────────────────────────────────

class MockLLMRouter:
    """
    模拟 Orchestrator 使用的 LLM。
    职责：分析用户意图，决定交给哪个 Subagent。
    """

    def route(self, user_message: str, system_prompt: str) -> dict:
        """
        返回路由决策。
        真实场景里 Orchestrator 调用强模型（Opus），成本较高，
        但只负责路由决策，输出 token 很少。
        """
        import re

        # 估算 token：system_prompt + user_message
        input_tokens = len(system_prompt) // 2 + len(user_message) // 2
        output_tokens = 30  # 路由决策输出很短

        multi_agent_usage.add(input_tokens, output_tokens)

        # Mock 路由逻辑
        msg = user_message.lower()
        if any(kw in msg for kw in ["退货", "退款", "政策", "规则", "条款"]):
            target = "policy_agent"
            reason = "涉及政策查询"
        elif any(kw in msg for kw in ["快递", "物流", "到了", "发货", "配送"]):
            target = "shipping_agent"
            reason = "涉及物流查询"
        else:
            target = "shipping_agent"   # 默认路由
            reason = "默认"

        print(f"  [Orchestrator] 路由决策：→ {target}（{reason}）"
              f"  [消耗：输入{input_tokens} 输出{output_tokens} token]")

        return {"target": target, "reason": reason}

    def synthesize(self, user_message: str, subagent_results: list[dict],
                   system_prompt: str) -> str:
        """
        汇总 Subagent 结果，生成最终回复。
        这一步消耗 token 较多，因为要把所有 Subagent 结果都放入上下文。
        """
        # 把所有 subagent 结果都要放进上下文
        context = json.dumps(subagent_results, ensure_ascii=False)
        input_tokens = len(system_prompt) // 2 + len(user_message) // 2 + len(context) // 2
        output_tokens = 80

        multi_agent_usage.add(input_tokens, output_tokens)

        # 从结果里取回复
        for result in subagent_results:
            if result.get("reply"):
                print(f"  [Orchestrator] 汇总回复"
                      f"  [消耗：输入{input_tokens} 输出{output_tokens} token]")
                return result["reply"]

        return "已处理您的请求。"


class MockLLMWorker:
    """
    模拟 Subagent 使用的 LLM（Sonnet，性价比优先）。
    """

    def __init__(self, agent_name: str, system_prompt: str):
        self.agent_name = agent_name
        self.system_prompt = system_prompt

    def process(self, task: str) -> dict:
        """
        处理分配到的任务，返回结果。
        Subagent 有自己的 system_prompt（专业知识），不需要包含全部规则。
        """
        input_tokens = len(self.system_prompt) // 2 + len(task) // 2
        output_tokens = 60

        multi_agent_usage.add(input_tokens, output_tokens)

        print(f"  [{self.agent_name}] 处理任务：{task[:30]}..."
              f"  [消耗：输入{input_tokens} 输出{output_tokens} token]")

        # Mock 返回
        if "policy" in self.agent_name.lower():
            return {
                "reply": "根据平台政策，普通商品支持7天无理由退货，需保持商品完好。定制商品不支持无理由退货。",
                "source": "售后政策第3条",
            }
        else:
            import re
            order_match = re.search(r"[A-Z]\d{4}", task)
            if order_match:
                return {
                    "reply": f"订单 {order_match.group()} 正在配送中，预计 2 天内到达。",
                    "order_id": order_match.group(),
                }
            return {
                "reply": "请提供订单号以便查询物流状态。",
            }


class MockSingleLLM:
    """
    模拟单 Agent 方案：一个模型处理所有任务。
    system_prompt 更长（包含所有规则），token 消耗不同。
    """

    def process(self, user_message: str, system_prompt: str) -> str:
        # 单 Agent：system_prompt 包含所有规则，更长
        input_tokens = len(system_prompt) // 2 + len(user_message) // 2
        output_tokens = 80

        single_agent_usage.add(input_tokens, output_tokens)

        print(f"  [SingleAgent] 处理消息"
              f"  [消耗：输入{input_tokens} 输出{output_tokens} token]")

        msg = user_message.lower()
        if any(kw in msg for kw in ["退货", "退款", "政策"]):
            return "根据平台政策，普通商品支持7天无理由退货，定制商品不支持。"
        else:
            import re
            order_match = re.search(r"[A-Z]\d{4}", user_message)
            if order_match:
                return f"订单 {order_match.group()} 正在配送中，预计 2 天内到达。"
            return "请提供订单号以便查询物流状态。"


# ── Subagent 定义 ─────────────────────────────────────────────────────────────
# 每个 Subagent 有自己的 system_prompt，只包含它需要的知识。
# 这是多 Agent 模式的核心优势：职责清晰，提示词精简。

class PolicyAgent:
    """
    专职处理政策和退货类问题。
    system_prompt 只包含售后政策知识，不包含物流查询规则。
    """
    SYSTEM_PROMPT = """你是售后政策专家，只处理退货、退款、政策相关问题。
规则：
- 引用具体政策条款，不猜测
- 定制商品不支持无理由退货
- 超过退货期的只能走申诉流程
不处理：物流查询、订单状态、账号问题"""

    def __init__(self):
        self.llm = MockLLMWorker("PolicyAgent", self.SYSTEM_PROMPT)

    def handle(self, task: str) -> dict:
        return self.llm.process(task)


class ShippingAgent:
    """
    专职处理物流和配送类问题。
    system_prompt 只包含物流查询知识。
    """
    SYSTEM_PROMPT = """你是物流查询专家，只处理快递、配送、物流状态问题。
规则：
- 没有订单号时先追问
- 不编造物流状态，只引用查询结果
- 工具失败时如实告知
不处理：退款、政策、账号问题"""

    def __init__(self):
        self.llm = MockLLMWorker("ShippingAgent", self.SYSTEM_PROMPT)

    def handle(self, task: str) -> dict:
        return self.llm.process(task)


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """
    负责路由决策和结果汇总。
    不直接处理业务，只做分发和整合。

    Handoff 机制：
    Orchestrator 分析用户意图，决定把任务交给哪个 Subagent（handoff）。
    Subagent 完成任务后把结果交回 Orchestrator（result return）。
    Orchestrator 汇总后生成最终回复。
    """

    SYSTEM_PROMPT = """你是客服调度系统。
职责：分析用户意图，路由到正确的专职 Agent。
可用 Agent：
- policy_agent：处理退货、退款、政策问题
- shipping_agent：处理物流、配送、订单查询
路由原则：一个问题只路由给一个 Agent，除非明确涉及多个领域。"""

    def __init__(self):
        self.router = MockLLMRouter()
        self.agents = {
            "policy_agent": PolicyAgent(),
            "shipping_agent": ShippingAgent(),
        }

    def run(self, user_message: str) -> str:
        print(f"\n[Orchestrator] 收到消息：{user_message}")

        # Step 1: 路由决策（Handoff）
        routing = self.router.route(user_message, self.SYSTEM_PROMPT)
        target = routing["target"]

        # Step 2: 执行 Handoff，把任务交给目标 Subagent
        if target not in self.agents:
            return f"没有找到处理 {target} 的 Agent"

        agent = self.agents[target]
        print(f"  → Handoff 到 {target}")
        result = agent.handle(user_message)

        # Step 3: 汇总结果
        final_reply = self.router.synthesize(
            user_message, [result], self.SYSTEM_PROMPT
        )

        return final_reply


# ── 单 Agent 方案（对照组） ───────────────────────────────────────────────────

class SingleAgent:
    """
    单 Agent 方案：一个模型处理所有类型的问题。
    system_prompt 包含所有规则，比每个 Subagent 的 prompt 都长。
    """

    # 注意：这个 prompt 是 PolicyAgent.SYSTEM_PROMPT + ShippingAgent.SYSTEM_PROMPT 的合并
    SYSTEM_PROMPT = """你是电商客服助手，处理所有类型的客服问题。
售后政策：
- 普通商品支持7天无理由退货，需保持商品完好
- 定制商品不支持无理由退货
- 超过退货期只能走申诉流程
物流查询：
- 没有订单号时先追问
- 不编造物流状态，只引用查询结果
- 工具失败时如实告知
通用规则：
- 引用具体政策条款，不猜测
- 退款、删号等高风险操作需人工审核"""

    def __init__(self):
        self.llm = MockSingleLLM()

    def run(self, user_message: str) -> str:
        print(f"\n[SingleAgent] 收到消息：{user_message}")
        reply = self.llm.process(user_message, self.SYSTEM_PROMPT)
        print(f"  回复：{reply}")
        return reply


# ── 运行和对比 ────────────────────────────────────────────────────────────────

def run_comparison(test_messages: list[str]):
    """
    用相同的消息集跑多 Agent 和单 Agent 两个方案，对比 token 消耗。
    """
    orchestrator = Orchestrator()
    single = SingleAgent()

    print("\n" + "="*60)
    print("多 Agent 方案")
    print("="*60)
    for msg in test_messages:
        reply = orchestrator.run(msg)
        print(f"💬 最终回复：{reply}\n")

    print("\n" + "="*60)
    print("单 Agent 方案（对照）")
    print("="*60)
    for msg in test_messages:
        reply = single.run(msg)
        print(f"💬 最终回复：{reply}\n")

    print("\n" + "="*60)
    print("结构开销对比（字符级估算，不代表厂商账单）")
    print("="*60)
    print(f"多 Agent 方案：{multi_agent_usage.summary()}")
    print(f"\n单 Agent 方案：{single_agent_usage.summary()}")
    extra_calls = multi_agent_usage.call_count - single_agent_usage.call_count
    extra_tokens = (
        multi_agent_usage.input_tokens + multi_agent_usage.output_tokens
        - single_agent_usage.input_tokens - single_agent_usage.output_tokens
    )
    print(f"\n多 Agent 额外调用：{extra_calls:+d} 次")
    print(f"多 Agent 额外估算 token：{extra_tokens:+d}")
    print(f"\n📌 结论：多 Agent 模式在简单场景下往往比单 Agent 更贵，")
    print(f"   因为 Orchestrator 的路由调用和汇总调用都有额外 token 消耗。")
    print(f"   只有当任务复杂度高、各专职 Agent 的 prompt 能显著压缩时才划算。")


def run_parallel_demo(user_message: str) -> dict:
    """用线程模拟两个相互独立的只读子任务并行执行。

    线程只是教学用的并发外壳，不等于任何厂商托管 Multi-agent API。
    真实系统还要处理取消、共享资源冲突、超时、结果仲裁和 trace parent。
    """
    global multi_agent_usage
    workers = [PolicyAgent(), ShippingAgent()]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker.handle, user_message) for worker in workers]
        results = [future.result() for future in futures]
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    # 明确的冲突规则：订单事实优先于政策解释；这里仅示范结构化汇总。
    return {
        "mode": "parallel_subagents",
        "elapsed_ms": elapsed_ms,
        "results": results,
        "arbitration": "policy source and shipping fact are retained separately",
    }


def main():
    test_messages = [
        "我的快递 A1001 到哪里了？",
        "定制商品可以退货吗？",
        "订单 A1003 的物流状态",
    ]
    run_comparison(test_messages)
    print("\n并行 Subagent 演示：")
    print(json.dumps(run_parallel_demo("订单 A1001 的物流和退货政策"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # ── 改动实验 ──────────────────────────────────────────────────────────────
    # 实验 1：把 test_messages 改成只包含一条消息，观察两种方案的 token 差距
    #         结论：消息越少，多 Agent 的额外开销占比越高
    #
    # 实验 2：给 Orchestrator.SYSTEM_PROMPT 加入和 Subagent 一样多的规则内容，
    #         观察 token 消耗变化——这模拟了"多 Agent 但 Orchestrator 塞了所有规则"的错误设计
    #
    # 实验 3：在 Orchestrator.run 里模拟把一个消息同时发给两个 Subagent（并行），
    #         观察 token 和延迟如何变化
    main()
