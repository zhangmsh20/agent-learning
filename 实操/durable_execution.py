"""第 6 章 2026-09 配套代码：可恢复执行、审批和幂等。

这是一个完全离线的运行时小实验。它模拟：
  1. 创建任务并保存 checkpoint；
  2. 在高风险动作前暂停等待审批；
  3. 进程重启后从序列化 checkpoint 恢复；
  4. 审批通过后执行副作用；
  5. 重试同一个 idempotency_key 不会重复创建工单。

生产系统应把 CheckpointStore 换成数据库/对象存储，并在恢复时重新做身份、权限和工具版本检查。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ApprovalState = Literal["not_required", "pending", "approved", "rejected"]


@dataclass
class TaskState:
    task_id: str
    checkpoint_id: str
    user_id: str
    action: str
    approval_state: ApprovalState = "pending"
    status: str = "waiting_approval"
    idempotency_key: str = ""
    result: dict[str, Any] | None = None
    events: list[str] = field(default_factory=list)


class CheckpointStore:
    """用 JSON 深拷贝模拟可跨进程保存的 checkpoint。"""

    def __init__(self):
        self._data: dict[str, str] = {}

    def save(self, state: TaskState) -> None:
        self._data[state.task_id] = json.dumps(asdict(state), ensure_ascii=False)

    def load(self, task_id: str) -> TaskState:
        raw = self._data[task_id]
        return TaskState(**json.loads(raw))

    def export(self) -> str:
        return json.dumps(self._data, ensure_ascii=False)

    @classmethod
    def import_store(cls, payload: str) -> "CheckpointStore":
        store = cls()
        store._data = json.loads(payload)
        return store


class IdempotentTicketTool:
    """副作用工具：同一个幂等键只产生一个工单。"""

    def __init__(self):
        self.created: dict[str, dict[str, Any]] = {}

    def create(self, *, user_id: str, summary: str, idempotency_key: str) -> dict[str, Any]:
        if idempotency_key in self.created:
            return {**self.created[idempotency_key], "replayed": True}
        ticket = {
            "ticket_id": f"TK-{len(self.created) + 1:04d}",
            "user_id": user_id,
            "summary": summary,
            "created_at": int(time.time()),
        }
        self.created[idempotency_key] = ticket
        return {**ticket, "replayed": False}


class DurableAgent:
    def __init__(self, store: CheckpointStore | None = None, tool: IdempotentTicketTool | None = None):
        self.store = store or CheckpointStore()
        self.tool = tool or IdempotentTicketTool()

    def start(self, task_id: str, user_id: str, summary: str) -> TaskState:
        state = TaskState(
            task_id=task_id,
            checkpoint_id=f"cp-{task_id}-1",
            user_id=user_id,
            action="create_support_ticket",
            idempotency_key=f"ticket:{task_id}",
            events=["task_started", "approval_requested"],
        )
        state.result = {"summary": summary}
        self.store.save(state)
        return state

    def approve(self, task_id: str, approved: bool) -> TaskState:
        state = self.store.load(task_id)
        if state.status != "waiting_approval":
            return state
        state.approval_state = "approved" if approved else "rejected"
        state.status = "ready" if approved else "rejected"
        state.events.append("approval_approved" if approved else "approval_rejected")
        state.checkpoint_id = f"cp-{task_id}-{len(state.events)}"
        self.store.save(state)
        return state

    def resume(self, task_id: str, *, force_retry: bool = False) -> TaskState:
        state = self.store.load(task_id)
        if state.status == "completed" and not force_retry:
            return state
        if state.approval_state != "approved":
            raise RuntimeError("任务尚未获得审批，不能执行副作用")
        result = self.tool.create(
            user_id=state.user_id,
            summary=state.result["summary"] if state.result else "",
            idempotency_key=state.idempotency_key,
        )
        state.result = result
        state.status = "completed"
        state.events.append("ticket_created_replayed" if result["replayed"] else "ticket_created")
        state.checkpoint_id = f"cp-{task_id}-{len(state.events)}"
        self.store.save(state)
        return state

    def cancel(self, task_id: str) -> TaskState:
        state = self.store.load(task_id)
        if state.status == "completed":
            raise RuntimeError("已完成任务不能取消；生产系统应走补偿流程")
        state.status = "cancelled"
        state.events.append("task_cancelled")
        self.store.save(state)
        return state


def main() -> None:
    agent = DurableAgent()
    first = agent.start("task-001", "U001", "物流延迟，请人工跟进")
    print("1) 已暂停：", first.status, first.checkpoint_id)

    # 模拟进程重启：只保留可序列化的 checkpoint 和工具存储。
    persisted = agent.store.export()
    restored = DurableAgent(CheckpointStore.import_store(persisted), agent.tool)
    restored.approve("task-001", True)
    done = restored.resume("task-001")
    replay = restored.resume("task-001", force_retry=True)
    print("2) 恢复完成：", done.status, done.result)
    print("3) 重复 resume：", replay.events[-1], "| 工单数：", len(restored.tool.created))


if __name__ == "__main__":
    main()
