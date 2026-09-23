"""
第6章配套代码：状态定义与跨节点传递

对应教材知识点：
  - 用 TypedDict 描述状态契约，让 IDE 和静态检查器发现字段问题
  - 状态字段在节点 A 写入、节点 B 读取的完整路径
  - 状态字段缺失时会发生什么（对应"状态失效"章节的理论）
  - 节点的单一职责：每个节点只做一件事，只修改它负责的字段

运行方式：
  pip install langgraph
  python 实操/state_graph.py

Mock 说明：
  LLM 的 API 调用被 mock_llm_call 函数替代。
  状态图的节点连接、状态传递、条件路由都是真实的 LangGraph 代码。
  本脚本专门隔离“状态图”知识点，因此始终使用本地 Mock LLM。
  真实模型接入放在综合项目中，不和状态传递实验混在一起。

图结构：
  START
    ↓
  extract_intent_node      # 识别意图和缺失字段
    ↓
  check_params_node        # 检查参数是否完整
    ↓ (条件路由)
  ┌─────────────────────┐
  │                     │
  ask_user_node     execute_tool_node   # 缺参数追问 / 有参数执行
  │                     │
  └──────────┬──────────┘
             ↓
         generate_reply_node            # 生成最终回复
             ↓
           END
"""

from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END


# ── 状态定义 ──────────────────────────────────────────────────────────────────
# 这是本章最核心的部分。
#
# 为什么用 TypedDict 而不是普通 dict？
#   - 字段有明确类型，IDE 和类型检查工具能发现问题
#   - 每个字段的含义一目了然
#   - 字段契约便于静态检查；TypedDict 本身不会在运行时自动校验
#
# 字段设计原则：
#   - 每个字段代表一个决策节点需要的信息
#   - Optional 的字段在初始化时给 None，避免 KeyError
#   - 不要把所有信息塞进一个字段（比如把订单号和用户 ID 都塞进 "params"）

class AgentState(TypedDict):
    # ── 输入 ──────────────────────────────────────────────────────────────
    user_message: str                    # 用户原始输入，只写入一次，节点只读

    # ── 意图识别结果 ──────────────────────────────────────────────────────
    intent: str | None                   # 识别出的意图标签，例如 "query_shipping"
    missing_fields: list[str]            # 当前缺少的必要参数，例如 ["order_id"]
    extracted_params: dict               # 从用户输入中提取到的参数

    # ── 执行结果 ──────────────────────────────────────────────────────────
    tool_result: dict | None             # 工具调用的返回值
    tool_error: str | None               # 工具调用失败时的错误原因

    # ── 输出 ──────────────────────────────────────────────────────────────
    reply: str | None                    # 最终回复文本
    needs_human: bool                    # 是否需要转人工

    # ── 路由控制 ──────────────────────────────────────────────────────────
    # 这个字段不对用户可见，只用于图的条件路由判断
    next_action: Literal["ask_user", "execute_tool"] | None


def make_initial_state(user_message: str) -> AgentState:
    """
    每次对话开始时创建初始状态。
    所有可选字段给 None 或空值，避免节点访问时 KeyError。

    常见错误：忘记初始化某个字段，节点运行时报 KeyError。
    改动实验：把某个字段从这里删掉，观察哪个节点会报错。
    """
    return AgentState(
        user_message=user_message,
        intent=None,
        missing_fields=[],
        extracted_params={},
        tool_result=None,
        tool_error=None,
        reply=None,
        needs_human=False,
        next_action=None,
    )


# ── Mock LLM 调用 ─────────────────────────────────────────────────────────────
# 只替换 LLM 调用本身，节点逻辑不变。

def mock_llm_call(task: str, context: dict) -> dict:
    """
    模拟 LLM 对不同任务的返回。
    真实场景里这里是 client.messages.create(...)。
    """
    import re

    if task == "extract_intent":
        msg = context["user_message"]
        order_match = re.search(r"[A-Z]\d{4}", msg)
        user_match = re.search(r"U\d{3}", msg)

        intent = "query_shipping"  # 默认意图
        if "退款" in msg:
            intent = "refund_request"
        elif "工单" in msg or "人工" in msg:
            intent = "create_ticket"

        missing = []
        params = {}

        if order_match:
            params["order_id"] = order_match.group()
        else:
            missing.append("order_id")

        if user_match:
            params["user_id"] = user_match.group()
        else:
            params["user_id"] = "U001"  # 实际场景从登录态获取，这里 mock

        return {"intent": intent, "missing_fields": missing, "extracted_params": params}

    if task == "generate_reply":
        tool_result = context.get("tool_result")
        tool_error = context.get("tool_error")
        intent = context.get("intent")

        if tool_error:
            return {"reply": f"查询时遇到问题：{tool_error}，建议稍后重试或联系人工客服。"}

        if tool_result and not tool_result.get("success"):
            message = tool_result.get("message", "工具执行失败")
            return {"reply": f"{message}，请核对后重试或联系人工客服。"}

        if tool_result and tool_result.get("success"):
            status = tool_result.get("status", "")
            location = tool_result.get("location", "")
            days = tool_result.get("estimated_days", 0)
            status_text = {
                "in_transit": f"正在配送中，当前位置：{location}，预计 {days} 天到达。",
                "delivered": "已签收。如有问题请在 7 天内联系我们。",
                "delayed": f"因 {location}，预计延迟 {days} 天，抱歉给您带来不便。",
            }.get(status, "状态异常，建议联系人工客服。")
            return {"reply": f"您的订单 {status_text}"}

        if intent == "refund_request":
            return {
                "reply": "退款需要人工审核。是否需要我为您创建人工工单？",
                "needs_human": True,
            }

        return {"reply": "已收到您的问题，正在处理中。"}

    return {}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

MOCK_ORDERS = {
    "A1001": {"status": "in_transit", "location": "上海转运中心", "estimated_days": 2},
    "A1002": {"status": "delivered", "location": "已签收", "estimated_days": 0},
    "A1003": {"status": "delayed", "location": "天气原因滞留杭州", "estimated_days": 5},
}


def run_query_shipping(order_id: str, user_id: str) -> dict:
    if order_id not in MOCK_ORDERS:
        return {"success": False, "error": "not_found",
                "message": f"未找到订单 {order_id}"}
    return {"success": True, "order_id": order_id, **MOCK_ORDERS[order_id]}


# ── 图节点定义 ────────────────────────────────────────────────────────────────
# 每个节点是一个函数：接收完整 state，返回要更新的字段（增量更新）。
# 节点只修改它负责的字段，不触碰其他字段。
# 这是 LangGraph 的设计：返回 dict，框架负责合并到 state。

def extract_intent_node(state: AgentState) -> dict:
    """
    节点职责：识别用户意图和缺失参数。
    读取：user_message
    写入：intent, missing_fields, extracted_params, next_action
    """
    print(f"\n[节点] extract_intent | 输入：{state['user_message'][:30]}...")

    result = mock_llm_call("extract_intent", {"user_message": state["user_message"]})

    next_action = "ask_user" if result["missing_fields"] else "execute_tool"

    print(f"  意图：{result['intent']} | 缺失：{result['missing_fields']} | 下一步：{next_action}")

    # 只返回这个节点负责修改的字段
    return {
        "intent": result["intent"],
        "missing_fields": result["missing_fields"],
        "extracted_params": result["extracted_params"],
        "next_action": next_action,
    }


def check_params_node(state: AgentState) -> dict:
    """
    节点职责：检查参数是否完整，决定路由方向。
    读取：missing_fields, intent
    写入：next_action（可能修正）

    这个节点是状态图里的"守门员"：
    即使 extract_intent 漏判了缺失字段，这里还有一次兜底检查。
    """
    print(f"\n[节点] check_params | 意图：{state['intent']} | 缺失字段：{state['missing_fields']}")

    # 高风险意图直接转人工，不走工具
    if state["intent"] == "refund_request":
        print("  → 退款请求，路由到 ask_user（转人工流程）")
        return {"next_action": "ask_user", "needs_human": True}

    if state["missing_fields"]:
        return {"next_action": "ask_user"}

    return {"next_action": "execute_tool"}


def ask_user_node(state: AgentState) -> dict:
    """
    节点职责：生成追问或转人工消息。
    读取：missing_fields, needs_human, intent
    写入：reply
    """
    print(f"\n[节点] ask_user | needs_human：{state['needs_human']}")

    if state["needs_human"]:
        reply = "退款需要人工审核。是否需要我为您创建人工工单？"
    elif "order_id" in state["missing_fields"]:
        reply = "我可以帮您查询，请提供订单号（格式如 A1001）。"
    else:
        missing = "、".join(state["missing_fields"])
        reply = f"还需要您提供：{missing}，才能继续处理。"

    print(f"  回复：{reply}")
    return {"reply": reply}


def execute_tool_node(state: AgentState) -> dict:
    """
    节点职责：调用工具，把结果写入状态。
    读取：intent, extracted_params
    写入：tool_result, tool_error

    关键设计：工具调用失败时写入 tool_error，而不是抛出异常。
    这样 generate_reply_node 能感知到失败并生成合适的回复，
    而不是让整个图崩溃。
    """
    print(f"\n[节点] execute_tool | 意图：{state['intent']}")
    print(f"  参数：{state['extracted_params']}")

    try:
        if state["intent"] == "query_shipping":
            result = run_query_shipping(**state["extracted_params"])
            print(f"  工具返回：{result}")
            return {"tool_result": result, "tool_error": None}
        else:
            # 未知意图的工具调用
            return {
                "tool_result": None,
                "tool_error": f"不支持的意图 {state['intent']}",
            }
    except TypeError as e:
        # 参数不匹配（例如 extracted_params 里缺少必要字段）
        return {"tool_result": None, "tool_error": f"参数错误：{e}"}
    except Exception as e:
        return {"tool_result": None, "tool_error": f"工具执行失败：{e}"}


def generate_reply_node(state: AgentState) -> dict:
    """
    节点职责：根据工具结果或状态生成最终回复。
    读取：tool_result, tool_error, intent, needs_human
    写入：reply（如果 ask_user_node 没有先写入的话）

    注意：如果 ask_user_node 已经写了 reply，这个节点不会覆盖它。
    （条件路由保证两个节点只有一个会运行）
    """
    print(f"\n[节点] generate_reply")

    result = mock_llm_call("generate_reply", {
        "tool_result": state["tool_result"],
        "tool_error": state["tool_error"],
        "intent": state["intent"],
    })

    reply = result.get("reply", "已处理您的请求。")
    print(f"  回复：{reply}")
    return {"reply": reply}


# ── 条件路由函数 ──────────────────────────────────────────────────────────────

def route_after_check(state: AgentState) -> Literal["ask_user", "execute_tool"]:
    """
    根据 state 里的 next_action 决定路由方向。
    这个函数只做路由判断，不修改状态。
    """
    return state["next_action"]


# ── 构建状态图 ────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("extract_intent", extract_intent_node)
    graph.add_node("check_params", check_params_node)
    graph.add_node("ask_user", ask_user_node)
    graph.add_node("execute_tool", execute_tool_node)
    graph.add_node("generate_reply", generate_reply_node)

    # 固定边
    graph.add_edge(START, "extract_intent")
    graph.add_edge("extract_intent", "check_params")

    # 条件路由：check_params 之后根据 next_action 分叉
    graph.add_conditional_edges(
        "check_params",
        route_after_check,
        {
            "ask_user": "ask_user",
            "execute_tool": "execute_tool",
        },
    )

    # 两条路径都汇入 generate_reply（ask_user 路径也要经过，用于 needs_human 场景）
    graph.add_edge("ask_user", END)          # 追问后直接结束，等用户补充
    graph.add_edge("execute_tool", "generate_reply")
    graph.add_edge("generate_reply", END)

    return graph.compile()


# ── 运行示例 ──────────────────────────────────────────────────────────────────

def run_scenario(app, description: str, user_message: str):
    print(f"\n{'='*60}")
    print(f"场景：{description}")
    print(f"{'='*60}")

    initial_state = make_initial_state(user_message)
    final_state = app.invoke(initial_state)

    print(f"\n最终状态（关键字段）：")
    print(f"  intent         = {final_state['intent']}")
    print(f"  missing_fields = {final_state['missing_fields']}")
    print(f"  tool_result    = {final_state['tool_result']}")
    print(f"  tool_error     = {final_state['tool_error']}")
    print(f"  needs_human    = {final_state['needs_human']}")
    print(f"\n💬 Agent 回复：{final_state['reply']}")


def main():
    app = build_graph()

    # 场景 1：缺少订单号，应追问
    run_scenario(app, "缺少订单号", "我的快递怎么还没到？")

    # 场景 2：有订单号，正常查询
    run_scenario(app, "正常查询", "帮我查一下订单 A1001 的状态")

    # 场景 3：订单延迟
    run_scenario(app, "延迟订单", "订单 A1003 到哪了？")

    # 场景 4：退款请求，应转人工
    run_scenario(app, "退款请求", "我要退款，订单 A1002")

    # 场景 5：订单号不存在
    run_scenario(app, "订单不存在", "查一下订单 Z9999")


if __name__ == "__main__":
    # ── 改动实验 ──────────────────────────────────────────────────────────────
    # 实验 1：在 make_initial_state 里删掉 "tool_error": None 这行，
    #         运行场景 5，观察 generate_reply_node 如何报 KeyError。
    #         这就是"状态字段未初始化"导致的典型失效。
    #
    # 实验 2：在 execute_tool_node 里把 except Exception 去掉，
    #         传入一个错误参数（比如把 extracted_params 清空），
    #         观察没有异常兜底时图会如何崩溃。
    #
    # 实验 3：把 check_params_node 里退款的路由改为 "execute_tool"，
    #         观察退款请求直接走工具调用时会发生什么。
    main()
