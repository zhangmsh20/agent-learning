"""
第5章配套代码：工具调用与失败兜底

对应教材知识点：
  - 工具 schema 的字段结构（name / description / input_schema）
  - Agent 拿到工具结果后的处理逻辑
  - 工具失败时不编造结果的兜底机制

运行方式：
  pip install anthropic
  python 实操/tool_calling.py

Mock 说明：
  LLM 的 API 调用被 MockLLMClient 替代。
  MockLLMClient 根据消息内容模拟两种决策：
    1. 调用工具（返回 tool_use block）
    2. 生成最终回复（返回 text block）
  工具函数本身是真实逻辑，包含正常返回和超时两种情况。
  设置 AI_AGENT_USE_MOCK=false，并通过环境变量提供 ANTHROPIC_API_KEY，
  可以切换到真实调用。不要把 API key 写进代码或提交到版本库。
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

# ── 配置 ──────────────────────────────────────────────────────────────────────

USE_MOCK = os.getenv("AI_AGENT_USE_MOCK", "true").lower() != "false"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# 模型名称变化很快，因此允许通过环境变量替换，不把教材绑定到永久型号。
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
# 教学演示默认稳定可复现；需要观察超时兜底时再显式开启。
SIMULATE_TIMEOUT = os.getenv("AI_AGENT_SIMULATE_TIMEOUT", "false").lower() == "true"


# ── 工具 schema 定义 ──────────────────────────────────────────────────────────
# 这是真实 Anthropic Tool Use 格式。
# description 写给模型看，决定它什么时候选这个工具。
# required 里的字段如果模型没给，调用会失败。

TOOLS = [
    {
        "name": "query_shipping",
        "description": (
            "根据订单号查询物流配送状态。"
            "仅在用户提供了订单号时调用。"
            "不知道订单号时不要猜测或调用此工具。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "订单编号，格式为字母开头加数字，例如 A1001",
                },
                "user_id": {
                    "type": "string",
                    "description": "当前用户 ID，用于鉴权，防止跨用户查询",
                },
            },
            "required": ["order_id", "user_id"],
        },
    },
    {
        "name": "create_support_ticket",
        "description": (
            "为无法自动处理的问题创建人工工单。"
            "在确认用户需要人工介入、且已收集足够信息后调用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "用户 ID"},
                "issue_type": {
                    "type": "string",
                    "enum": ["shipping_delay", "wrong_item", "refund_request", "other"],
                    "description": "问题类型",
                },
                "summary": {"type": "string", "description": "问题简述，50字以内"},
            },
            "required": ["user_id", "issue_type", "summary"],
        },
    },
]


# ── 真实工具函数 ───────────────────────────────────────────────────────────────
# 这里是真实的业务逻辑，不做 mock。
# 工具函数统一返回 dict，包含 success 字段供 Agent 判断。

@dataclass
class ShippingInfo:
    order_id: str
    status: str
    location: str
    estimated_days: int


# 模拟订单数据库
MOCK_ORDERS: dict[str, ShippingInfo] = {
    "A1001": ShippingInfo("A1001", "in_transit", "上海转运中心", 2),
    "A1002": ShippingInfo("A1002", "delivered", "已签收", 0),
    "A1003": ShippingInfo("A1003", "delayed", "因天气原因滞留杭州", 5),
}


def query_shipping(order_id: str, user_id: str) -> dict[str, Any]:
    """
    查询物流状态。
    真实场景里这里是 HTTP 调用外部物流 API。
    用随机超时模拟真实网络的不可靠性。
    """
    if SIMULATE_TIMEOUT:
        return {
            "success": False,
            "error": "timeout",
            "message": "物流查询服务暂时无响应，请稍后重试",
        }

    if order_id not in MOCK_ORDERS:
        return {
            "success": False,
            "error": "not_found",
            "message": f"未找到订单 {order_id}，请确认订单号是否正确",
        }

    info = MOCK_ORDERS[order_id]
    return {
        "success": True,
        "order_id": info.order_id,
        "status": info.status,
        "location": info.location,
        "estimated_days": info.estimated_days,
    }


def create_support_ticket(user_id: str, issue_type: str, summary: str) -> dict[str, Any]:
    """创建人工工单，返回工单号。"""
    ticket_id = f"TK{int(time.time())}"
    print(f"  [工单系统] 创建工单 {ticket_id}：{issue_type} / {summary}")
    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": "人工工单已创建，人工客服将在 2 小时内联系您",
    }


# 工具名称到函数的映射，供 Agent 执行时查找
TOOL_REGISTRY: dict[str, callable] = {
    "query_shipping": query_shipping,
    "create_support_ticket": create_support_ticket,
}


# ── Mock LLM 客户端 ────────────────────────────────────────────────────────────
# 替换真实 API 调用的薄层 mock。
# 只模拟"模型在什么情况下选哪个工具"和"最终回复的结构"。
# 真实 API 返回的数据结构完全一致，切换时不需要改 Agent 代码。

@dataclass
class ContentBlock:
    """对应 Anthropic API 返回的 content block"""
    type: str  # "text" | "tool_use"
    text: str | None = None
    # tool_use 字段
    id: str | None = None
    name: str | None = None
    input: dict | None = None


@dataclass
class MockMessage:
    """对应 Anthropic API 返回的 Message 对象"""
    content: list[ContentBlock]
    stop_reason: str  # "tool_use" | "end_turn"


class MockLLMClient:
    """
    轻量 mock：只替换 messages.create 这一个调用。
    根据最后一条用户消息的内容，决定模型的"意图"。
    """

    def __init__(self):
        self.messages = self  # 模拟 client.messages.create 的调用链

    def create(self, model: str, max_tokens: int,
               system: str, messages: list, tools: list) -> MockMessage:

        last_user_content = self._extract_last_user_text(messages)

        # 如果消息里包含订单号格式（字母+数字），模拟模型决定调用工具
        import re
        order_match = re.search(r"[A-Z]\d{4}", last_user_content)

        if order_match and "工单" in last_user_content:
            return self._mock_create_ticket(last_user_content)
        elif order_match:
            return self._mock_query_shipping(order_match.group(), last_user_content)
        elif any(kw in last_user_content for kw in ["没到", "快递", "物流", "发货"]):
            # 缺少订单号，模拟模型追问
            return MockMessage(
                content=[ContentBlock(
                    type="text",
                    text="我可以帮您查询物流状态，请提供您的订单号（格式如 A1001）。",
                )],
                stop_reason="end_turn",
            )
        else:
            # 工具结果已在上下文中，模拟模型生成最终回复
            return self._mock_final_response(messages)

    def _mock_query_shipping(self, order_id: str, content: str) -> MockMessage:
        return MockMessage(
            content=[ContentBlock(
                type="tool_use",
                id=f"tool_{int(time.time())}",
                name="query_shipping",
                input={"order_id": order_id, "user_id": "U001"},
            )],
            stop_reason="tool_use",
        )

    def _mock_create_ticket(self, content: str) -> MockMessage:
        return MockMessage(
            content=[ContentBlock(
                type="tool_use",
                id=f"tool_{int(time.time())}",
                name="create_support_ticket",
                input={
                    "user_id": "U001",
                    "issue_type": "shipping_delay",
                    "summary": "用户反映订单长时间未到，需要人工跟进",
                },
            )],
            stop_reason="tool_use",
        )

    def _mock_final_response(self, messages: list) -> MockMessage:
        # 从消息历史里找工具结果，生成对应的回复
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            result = json.loads(block.get("content", "{}"))
                            return self._generate_reply_from_result(result)
        return MockMessage(
            content=[ContentBlock(type="text", text="有什么可以帮您的吗？")],
            stop_reason="end_turn",
        )

    def _generate_reply_from_result(self, result: dict) -> MockMessage:
        if not result.get("success"):
            error = result.get("error", "unknown")
            if error == "timeout":
                text = "物流查询服务暂时不可用，建议您稍后重试或联系人工客服。"
            elif error == "not_found":
                text = f"{result.get('message', '订单未找到')}，请核对后重试。"
            else:
                text = "查询时遇到问题，已为您创建工单，客服将尽快跟进。"
        elif "ticket_id" in result:
            message = result.get("message", "人工工单已创建，客服将尽快联系您")
            text = f"{message}（工单号：{result['ticket_id']}）"
        elif "status" in result:
            status_map = {
                "in_transit": f"您的订单正在配送中，当前位置：{result['location']}，预计 {result['estimated_days']} 天内到达。",
                "delivered": "您的订单已签收，如有问题请在签收后 7 天内联系我们。",
                "delayed": f"您的订单因 {result['location']}，预计延迟 {result['estimated_days']} 天，给您带来不便深表歉意。",
            }
            text = status_map.get(result["status"], "已查询到订单信息，请以实际配送为准。")
        else:
            text = result.get("message", "操作已完成。")

        return MockMessage(
            content=[ContentBlock(type="text", text=text)],
            stop_reason="end_turn",
        )

    def _extract_last_user_text(self, messages: list) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                    return " ".join(texts)
        return ""


# ── Agent 核心逻辑 ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是电商平台客服助手。

规则：
1. 查询物流前必须有订单号，没有订单号时先追问用户。
2. 工具返回失败时，如实告知用户，不编造状态。
3. 实际退款、删除账号等高风险操作必须转人工，不自动执行。
4. 回复简洁，不超过 3 句话。
"""


class CustomerServiceAgent:
    """
    单轮工具调用 Agent。
    核心循环：模型决策 → 执行工具 → 把结果交回模型 → 生成回复。
    """

    MAX_TOOL_CALLS = 3  # 防止无限循环，每次对话最多调用工具 3 次

    def __init__(self, use_mock: bool = True):
        if use_mock:
            self.client = MockLLMClient()
        else:
            import anthropic
            if not ANTHROPIC_API_KEY:
                raise ValueError(
                    "真实调用需要设置 ANTHROPIC_API_KEY；"
                    "也可以保持 AI_AGENT_USE_MOCK=true 运行离线实验。"
                )
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        self.system = SYSTEM_PROMPT
        self.tools = TOOLS

    def run(self, user_message: str) -> str:
        """
        处理一条用户消息，返回最终回复文本。
        """
        print(f"\n{'='*60}")
        print(f"用户：{user_message}")
        print(f"{'='*60}")

        messages = [{"role": "user", "content": user_message}]
        tool_call_count = 0

        while True:
            # ── 1. 调用模型（或 mock） ─────────────────────────────────────
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=self.system,
                messages=messages,
                tools=self.tools,
            )

            # ── 2. 判断模型的决策 ──────────────────────────────────────────
            if response.stop_reason == "end_turn":
                # 模型认为任务完成，取出文本回复
                final_text = next(
                    (b.text for b in response.content if b.type == "text"), ""
                )
                print(f"\nAgent：{final_text}")
                return final_text

            if response.stop_reason == "tool_use":
                if tool_call_count >= self.MAX_TOOL_CALLS:
                    # ── 兜底：工具调用次数超限 ────────────────────────────
                    # 关键设计：超限时不让模型继续，直接返回安全回复。
                    # 不加这个限制，ReAct 循环可能无限调用工具。
                    fallback = "处理您的请求时遇到一些问题，已为您转接人工客服，请稍候。"
                    print(f"\nAgent（兜底）：{fallback}")
                    return fallback

                # ── 3. 执行工具调用 ────────────────────────────────────────
                tool_results = []
                # 把模型这轮的输出加入消息历史（包括它的工具调用意图）
                messages.append({
                    "role": "assistant",
                    "content": [
                        {"type": b.type, "id": b.id, "name": b.name, "input": b.input}
                        if b.type == "tool_use"
                        else {"type": "text", "text": b.text}
                        for b in response.content
                    ],
                })

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_call_count += 1
                    print(f"\n  → 调用工具：{block.name}({json.dumps(block.input, ensure_ascii=False)})")

                    # 查找工具函数并执行
                    tool_fn = TOOL_REGISTRY.get(block.name)
                    if tool_fn is None:
                        # 工具不存在：告知模型，让它决定下一步
                        result = {"success": False, "error": "tool_not_found",
                                  "message": f"工具 {block.name} 不存在"}
                    else:
                        try:
                            result = tool_fn(**block.input)
                        except Exception as e:
                            # ── 兜底：工具抛出异常 ────────────────────────
                            # 工具失败不能让 Agent 崩溃，把错误信息告知模型。
                            result = {"success": False, "error": "exception",
                                      "message": str(e)}

                    print(f"  ← 工具返回：{json.dumps(result, ensure_ascii=False)}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                # ── 4. 把工具结果放回消息，让模型继续决策 ──────────────────
                messages.append({"role": "user", "content": tool_results})


# ── 运行示例 ──────────────────────────────────────────────────────────────────

def main():
    agent = CustomerServiceAgent(use_mock=USE_MOCK)

    # 场景 1：缺少订单号 → 模型应追问
    agent.run("我的快递怎么还没到？")

    # 场景 2：提供订单号，物流正常
    agent.run("订单 A1001 的物流到哪里了？")

    # 场景 3：订单延迟，用户要求转人工
    agent.run("订单 A1003 延迟太久了，帮我建个工单")

    # 场景 4：订单号不存在
    agent.run("帮我查一下订单 Z9999 的状态")


if __name__ == "__main__":
    # ── 改动实验 ──────────────────────────────────────────────────────────────
    # 实验 1：把 MAX_TOOL_CALLS 改成 0，观察所有工具调用都走兜底
    # 实验 2：运行 AI_AGENT_SIMULATE_TIMEOUT=true python 实操/tool_calling.py，
    #          观察 Agent 如何处理工具超时而不编造结果
    # 实验 3：设置 AI_AGENT_USE_MOCK=false 和 ANTHROPIC_API_KEY，
    #          观察真实模型的工具选择和回复质量
    main()
