from __future__ import annotations

from ..schemas import MemoryRetrieval, TaskContext, TrajectoryStep
from .base import MemorySystem


class NoneMemory(MemorySystem):
    """A control group: no persistence and no cross-session retrieval."""

    mode = "none"

    def query(self, task: TaskContext) -> MemoryRetrieval:
        return MemoryRetrieval()

    def observe(self, task: TaskContext, trajectory: list[TrajectoryStep], trajectory_id: str) -> None:
        return None
