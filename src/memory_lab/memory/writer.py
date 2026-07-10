"""Deterministic extraction of reusable procedural memory from a trajectory."""

from __future__ import annotations

from datetime import datetime, timezone

from ..schemas import MemoryCard, TaskContext, TrajectoryStep
from .manager import MemoryManager, ManagementResult
from .store import MemoryStore


class DeterministicWriter:
    def __init__(self, store: MemoryStore, manager: MemoryManager) -> None:
        self.store = store
        self.manager = manager

    def extract_and_store(
        self, task: TaskContext, trajectory: list[TrajectoryStep], trajectory_id: str
    ) -> ManagementResult | None:
        errors = [step.result.error for step in trajectory if step.result.error]
        if not {"E_ENV_REQUIRED", "E_FIXTURE_REQUIRED"}.issubset(set(errors)):
            return None
        now = datetime.now(timezone.utc)
        candidate = MemoryCard(
            memory_id=self.store.next_memory_id(),
            memory_type="procedural",
            title="demo-project integration test workflow",
            content=(
                "Before running integration tests in demo-project, set APP_ENV=test, "
                "then initialize test data. This prevents E_ENV_REQUIRED and "
                "E_FIXTURE_REQUIRED."
            ),
            problem_signature=["E_ENV_REQUIRED", "E_FIXTURE_REQUIRED"],
            procedure=[
                "set_env(APP_ENV, test)",
                "init_test_data()",
                "run_integration_tests(module)",
            ],
            expected_outcome="integration tests pass",
            project_id=task.project_id,
            source_kind="verified_tool_trajectory",
            source_id=trajectory_id,
            confidence=0.95,
            trust_level="verified",
            risk_level="low",
            valid_from=now,
            created_at=now,
            updated_at=now,
        )
        return self.manager.add_or_patch(candidate)
