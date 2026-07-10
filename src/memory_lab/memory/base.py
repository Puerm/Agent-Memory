"""The shared protocol for memory strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import MemoryRetrieval, TaskContext, TrajectoryStep


class MemorySystem(ABC):
    mode: str

    @abstractmethod
    def query(self, task: TaskContext) -> MemoryRetrieval:
        raise NotImplementedError

    @abstractmethod
    def observe(self, task: TaskContext, trajectory: list[TrajectoryStep], trajectory_id: str) -> None:
        raise NotImplementedError
