"""Extension seam for a future tool-calling LLM planner.

The shipped demonstration uses :class:`memory_lab.agent.DemoAgent` so its
outcome is deterministic.  Replacing it with a model client must preserve the
same task, tool schemas, prompt contract, temperature, and step budget across
all three memory strategies.
"""

from __future__ import annotations

from typing import Protocol

from .schemas import Action, MemoryCard, TaskContext


class ModelClient(Protocol):
    def decide(
        self,
        task: TaskContext,
        tool_schemas: list[str],
        memories: list[MemoryCard],
        trajectory: list[tuple[Action, dict]],
    ) -> Action: ...
