"""Append-only raw event storage for replayable evidence."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .schemas import Action, Event, ToolResult


class EventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> Event:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
        return event

    def append_event(
        self,
        *,
        trajectory_id: str,
        session_id: str,
        producer: str,
        event_type: str,
        content: dict,
        caused_by_event_id: str | None = None,
    ) -> Event:
        return self.append(
            Event(
                event_id=uuid4().hex,
                trajectory_id=trajectory_id,
                session_id=session_id,
                producer=producer,  # type: ignore[arg-type]
                event_type=event_type,  # type: ignore[arg-type]
                caused_by_event_id=caused_by_event_id,
                content=content,
            )
        )

    def record_tool_exchange(
        self,
        *,
        trajectory_id: str,
        session_id: str,
        action: Action,
        result: ToolResult,
    ) -> tuple[Event, Event]:
        call = self.append_event(
            trajectory_id=trajectory_id,
            session_id=session_id,
            producer="agent",
            event_type="tool_call",
            content={"tool_name": action.tool_name, "arguments": action.arguments},
        )
        observation = self.append_event(
            trajectory_id=trajectory_id,
            session_id=session_id,
            producer="tool",
            event_type="tool_result",
            caused_by_event_id=call.event_id,
            content={"tool_name": action.tool_name, **result.model_dump(mode="json")},
        )
        return call, observation

    def events_for(self, trajectory_id: str) -> list[Event]:
        if not self.path.exists():
            return []
        events: list[Event] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            event = Event.model_validate(json.loads(line))
            if event.trajectory_id == trajectory_id:
                events.append(event)
        return events
