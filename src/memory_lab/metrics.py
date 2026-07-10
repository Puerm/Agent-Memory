"""Small append-only metrics collector for comparison reports."""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import RunResult


class MetricsCollector:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, result: RunResult) -> None:
        payload = result.model_dump(mode="json", exclude={"trajectory", "decisions"})
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
