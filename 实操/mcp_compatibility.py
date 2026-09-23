"""第 5 章 2026-09 配套代码：MCP 2026-07-28 多轮工具结果。

用纯 Python 演示 `resultType: input_required`：服务端发现缺少 region，
客户端补充 inputResponses 后再次调用。它不是 MCP Server，也不替代 SDK；
目的是先理解协议状态机、结构化结果和显式 handle。
"""

from __future__ import annotations

from typing import Any


PROTOCOL_VERSION = "2026-07-28"


def server_discover() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": {"name": "order-service", "version": "2.0"},
        "capabilities": {"tools": {"listChanged": True}},
    }


def call_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    if not arguments.get("region"):
        return {
            "resultType": "input_required",
            "inputRequests": [{"name": "region", "reason": "订单服务需要区域路由"}],
            "requestState": {"order_id": arguments.get("order_id")},
        }
    return {
        "resultType": "complete",
        "structuredContent": {
            "order_id": arguments["order_id"],
            "status": "in_transit",
            "location": f"{arguments['region']} 转运中心",
        },
        "_meta": {"traceparent": "00-demo-trace-01"},
    }


def main() -> None:
    print("discover:", server_discover())
    first = call_tool({"order_id": "A1001"})
    print("round 1:", first)
    assert first["resultType"] == "input_required"
    second = call_tool({"order_id": first["requestState"]["order_id"], "region": "华东"})
    print("round 2:", second)
    assert second["resultType"] == "complete"
    assert second["structuredContent"]["order_id"] == "A1001"


if __name__ == "__main__":
    main()
