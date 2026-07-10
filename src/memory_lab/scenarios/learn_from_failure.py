"""Task builders deliberately create a fresh session on every invocation."""

from __future__ import annotations

from uuid import uuid4

from ..schemas import TaskContext


SCENARIOS = {
    "learn-1": ("Run integration tests for the payments module.", "payments"),
    "learn-2": ("Run integration tests for the orders module.", "orders"),
    "injection": ("Run integration tests for the payments module.", "payments"),
}


def build_learning_task(scenario: str) -> TaskContext:
    try:
        text, _ = SCENARIOS[scenario]
    except KeyError as error:
        raise ValueError(f"Unknown scenario: {scenario}") from error
    return TaskContext(
        task_id=f"task-{scenario}-{uuid4().hex[:8]}",
        task_text=text,
        project_id="demo-project",
        session_id=f"session-{uuid4().hex[:12]}",
    )
