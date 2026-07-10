"""Pydantic contracts shared by the memory-lab components."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Event(BaseModel):
    event_id: str
    trajectory_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    producer: Literal["user", "agent", "tool", "system"]
    event_type: Literal[
        "user_request", "agent_message", "tool_call", "tool_result", "system_event"
    ]
    caused_by_event_id: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)


class TaskContext(BaseModel):
    task_id: str
    task_text: str
    project_id: str
    session_id: str
    intent: str = "run_integration_tests"
    allowed_tools: list[str] = Field(
        default_factory=lambda: [
            "inspect_project",
            "set_env",
            "init_test_data",
            "run_integration_tests",
            "read_error",
        ]
    )
    risk_level: Literal["low", "medium", "high"] = "low"
    current_time: datetime = Field(default_factory=utc_now)


class MemoryCard(BaseModel):
    memory_id: str
    memory_type: Literal["episodic", "semantic", "procedural", "prospective", "policy"]
    title: str
    content: str
    problem_signature: list[str] = Field(default_factory=list)
    procedure: list[str] = Field(default_factory=list)
    expected_outcome: str | None = None

    user_id: str | None = None
    project_id: str | None = None
    session_id: str | None = None

    source_kind: str
    source_id: str
    confidence: float = Field(ge=0, le=1)
    trust_level: Literal["verified", "trusted", "untrusted"]
    risk_level: Literal["low", "medium", "high"]

    valid_from: datetime = Field(default_factory=utc_now)
    valid_to: datetime | None = None
    status: Literal["active", "superseded", "revoked"] = "active"

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime | None = None
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0


class AdmissionDecision(BaseModel):
    memory_id: str
    admitted: bool
    semantic_score: float
    final_score: float | None = None
    reason_codes: list[str] = Field(default_factory=list)


class MemoryRetrieval(BaseModel):
    cards: list[MemoryCard] = Field(default_factory=list)
    raw_contexts: list[str] = Field(default_factory=list)
    decisions: list[AdmissionDecision] = Field(default_factory=list)


class Action(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    ok: bool
    task_complete: bool = False
    error: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)


class TrajectoryStep(BaseModel):
    action: Action
    result: ToolResult
    call_event_id: str
    result_event_id: str


class RunResult(BaseModel):
    trajectory_id: str
    session_id: str
    scenario: str
    mode: Literal["none", "naive", "governed"]
    success: bool
    tool_calls: int
    failed_tool_calls: int
    estimated_memory_tokens: int
    elapsed_ms: float
    errors: list[str] = Field(default_factory=list)
    admitted_memory_ids: list[str] = Field(default_factory=list)
    decisions: list[AdmissionDecision] = Field(default_factory=list)
    trajectory: list[TrajectoryStep] = Field(default_factory=list)
