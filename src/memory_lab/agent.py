"""A deterministic planner that makes memory effects measurable without an LLM."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from .environment.demo_project import DemoProjectEnvironment
from .events import EventStore
from .memory.base import MemorySystem
from .memory.embeddings import estimate_tokens
from .schemas import Action, RunResult, TaskContext, ToolResult, TrajectoryStep


class DemoAgent:
    def __init__(self, environment: DemoProjectEnvironment, event_store: EventStore) -> None:
        self.environment = environment
        self.event_store = event_store

    def run_task(self, task: TaskContext, memory: MemorySystem, scenario: str) -> RunResult:
        started = perf_counter()
        trajectory_id = f"run-{uuid4().hex[:12]}"
        retrieval = memory.query(task)
        self.event_store.append_event(
            trajectory_id=trajectory_id,
            session_id=task.session_id,
            producer="user",
            event_type="user_request",
            content={"task": task.task_text, "scenario": scenario},
        )

        trajectory: list[TrajectoryStep] = []
        if self._contains_unsafe_naive_instruction(retrieval.raw_contexts):
            # This is the intentionally unsafe baseline: a retrieved raw trace can
            # influence a dangerous action.  The environment remains safe.
            self._execute(
                task,
                trajectory_id,
                trajectory,
                Action(
                    tool_name="run_integration_tests",
                    arguments={"module": self._module(task), "force": True},
                ),
            )
        elif retrieval.cards or self._contains_reusable_raw_workflow(retrieval.raw_contexts):
            self._execute_known_workflow(task, trajectory_id, trajectory)
        else:
            self._execute_discovery_workflow(task, trajectory_id, trajectory)

        memory.observe(task, trajectory, trajectory_id)
        errors = [step.result.error for step in trajectory if step.result.error]
        success = any(step.result.task_complete for step in trajectory)
        memory_text = "\n".join([card.content for card in retrieval.cards] + retrieval.raw_contexts)
        return RunResult(
            trajectory_id=trajectory_id,
            session_id=task.session_id,
            scenario=scenario,
            mode=memory.mode,  # type: ignore[arg-type]
            success=success,
            tool_calls=len(trajectory),
            failed_tool_calls=sum(not step.result.ok for step in trajectory),
            estimated_memory_tokens=estimate_tokens(memory_text),
            elapsed_ms=round((perf_counter() - started) * 1000, 2),
            errors=[error for error in errors if error],
            admitted_memory_ids=[card.memory_id for card in retrieval.cards]
            + [decision.memory_id for decision in retrieval.decisions if decision.admitted and decision.memory_id.startswith("raw-")],
            decisions=retrieval.decisions,
            trajectory=trajectory,
        )

    def _execute_discovery_workflow(
        self, task: TaskContext, trajectory_id: str, trajectory: list[TrajectoryStep]
    ) -> None:
        module = self._module(task)
        self._execute(task, trajectory_id, trajectory, Action(tool_name="run_integration_tests", arguments={"module": module}))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="read_error", arguments={"error_id": "E_ENV_REQUIRED"}))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="set_env", arguments={"key": "APP_ENV", "value": "test"}))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="run_integration_tests", arguments={"module": module}))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="read_error", arguments={"error_id": "E_FIXTURE_REQUIRED"}))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="init_test_data"))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="run_integration_tests", arguments={"module": module}))

    def _execute_known_workflow(
        self, task: TaskContext, trajectory_id: str, trajectory: list[TrajectoryStep]
    ) -> None:
        module = self._module(task)
        self._execute(task, trajectory_id, trajectory, Action(tool_name="set_env", arguments={"key": "APP_ENV", "value": "test"}))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="init_test_data"))
        self._execute(task, trajectory_id, trajectory, Action(tool_name="run_integration_tests", arguments={"module": module}))

    def _execute(
        self,
        task: TaskContext,
        trajectory_id: str,
        trajectory: list[TrajectoryStep],
        action: Action,
    ) -> ToolResult:
        if action.tool_name not in task.allowed_tools:
            result = ToolResult(ok=False, error="TOOL_NOT_ALLOWED", content={"tool": action.tool_name})
        else:
            result = self.environment.execute(action)
        call, observation = self.event_store.record_tool_exchange(
            trajectory_id=trajectory_id, session_id=task.session_id, action=action, result=result
        )
        trajectory.append(
            TrajectoryStep(
                action=action,
                result=result,
                call_event_id=call.event_id,
                result_event_id=observation.event_id,
            )
        )
        return result

    @staticmethod
    def _contains_unsafe_naive_instruction(raw_contexts: list[str]) -> bool:
        return any("force=true" in content.lower() or "force mode" in content.lower() for content in raw_contexts)

    @staticmethod
    def _contains_reusable_raw_workflow(raw_contexts: list[str]) -> bool:
        text = "\n".join(raw_contexts).lower()
        return "tool=set_env" in text and "tool=init_test_data" in text

    @staticmethod
    def _module(task: TaskContext) -> str:
        for module in ("payments", "orders"):
            if module in task.task_text.lower():
                return module
        return "payments"
