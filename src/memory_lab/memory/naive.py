"""The intentionally unsafe baseline: rank raw traces only by similarity."""

from __future__ import annotations

from ..schemas import AdmissionDecision, MemoryRetrieval, TaskContext, TrajectoryStep
from .base import MemorySystem
from .embeddings import similarity
from .store import MemoryStore


class NaiveMemory(MemorySystem):
    mode = "naive"

    def __init__(self, store: MemoryStore, top_k: int = 3) -> None:
        self.store = store
        self.top_k = top_k

    def query(self, task: TaskContext) -> MemoryRetrieval:
        ranked = []
        for record in self.store.list_naive_records():
            record_id = str(record["record_id"])
            content = str(record["content"])
            score = similarity(task.task_text, content)
            ranked.append((record_id, content, score))
        ranked.sort(key=lambda item: item[2], reverse=True)
        selected = ranked[: self.top_k]
        return MemoryRetrieval(
            raw_contexts=[content for _, content, _ in selected],
            decisions=[
                AdmissionDecision(
                    memory_id=record_id,
                    admitted=True,
                    semantic_score=score,
                    final_score=score,
                    reason_codes=["TOP_K_SIMILARITY_ONLY"],
                )
                for record_id, _, score in selected
            ],
        )

    def observe(self, task: TaskContext, trajectory: list[TrajectoryStep], trajectory_id: str) -> None:
        lines = [f"Task: {task.task_text}", f"Project: {task.project_id}"]
        for step in trajectory:
            lines.append(
                f"tool={step.action.tool_name} arguments={step.action.arguments} "
                f"ok={step.result.ok} error={step.result.error}"
            )
        self.store.put_naive_record(f"raw-{trajectory_id}", task.project_id, "\n".join(lines))
