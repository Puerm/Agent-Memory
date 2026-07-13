"""Lifecycle manager for ADD, PATCH, INVALIDATE and NOOP decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import difflib

from ..schemas import MemoryCard
from .store import MemoryStore


@dataclass(frozen=True)
class ManagementResult:
    operation: str
    card: MemoryCard


class MemoryManager:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def add_or_patch(self, candidate: MemoryCard) -> ManagementResult:
        for existing in self.store.active_cards():
            same_scope = existing.project_id == candidate.project_id
            same_procedure = existing.procedure == candidate.procedure
            if same_scope and same_procedure and existing.memory_type == candidate.memory_type:
                return ManagementResult("NOOP", existing)
            if same_scope and existing.title == candidate.title:
                updated = candidate.model_copy(
                    update={
                        "memory_id": existing.memory_id,
                        "created_at": existing.created_at,
                        "updated_at": datetime.now(existing.updated_at.tzinfo),
                    }
                )
                self.store.put_card(updated)
                return ManagementResult("PATCH", updated)
        self.store.put_card(candidate)
        return ManagementResult("ADD", candidate)

    def invalidate(self, memory_id: str) -> MemoryCard:
        card = self.store.get_card(memory_id)
        if card is None:
            raise KeyError(memory_id)
        revoked = card.model_copy(update={"status": "revoked", "updated_at": datetime.now(card.updated_at.tzinfo)})
        self.store.put_card(revoked)
        return revoked

    def promote(self, memory_id: str, target: str) -> MemoryCard:
        allowed = {"candidate": "tested", "tested": "canary", "canary": "active"}
        card = self._require(memory_id)
        if allowed.get(card.release_status) != target:
            raise ValueError(f"invalid release transition: {card.release_status} -> {target}")
        updated = card.model_copy(update={"release_status": target, "updated_at": datetime.now(card.updated_at.tzinfo)})
        self.store.put_card(updated)
        return updated

    def rollback(self, memory_id: str) -> MemoryCard:
        card = self._require(memory_id)
        revoked = card.model_copy(update={"status": "revoked", "release_status": "revoked",
            "updated_at": datetime.now(card.updated_at.tzinfo)})
        self.store.put_card(revoked)
        if card.supersedes:
            previous = self._require(card.supersedes).model_copy(update={"status": "active", "release_status": "active"})
            self.store.put_card(previous)
            return previous
        return revoked

    def consolidate(self, memory_id: str, variant: str = "overgeneralized") -> MemoryCard:
        """Create a versioned consolidation candidate; the demo variant intentionally regresses."""
        previous = self._require(memory_id)
        if variant != "overgeneralized":
            raise ValueError("supported variant: overgeneralized")
        now = datetime.now(previous.updated_at.tzinfo)
        procedure = ["set_env(ENV, test)" if step.startswith("set_env(APP_ENV") else step
                     for step in previous.procedure]
        candidate = previous.model_copy(update={
            "memory_id": self.store.next_memory_id(), "version": previous.version + 1,
            "supersedes": previous.memory_id, "procedure": procedure,
            "content": previous.content.replace("APP_ENV=test", "the environment configured"),
            "source_kind": "memory_consolidation", "source_id": previous.memory_id,
            "confidence": 0.80, "release_status": "active", "status": "active",
            "created_at": now, "updated_at": now, "use_count": 0,
            "success_count": 0, "failure_count": 0, "last_used_at": None,
        })
        superseded = previous.model_copy(update={"status": "superseded", "updated_at": now})
        self.store.put_card(superseded)
        self.store.put_card(candidate)
        return candidate

    def diff(self, old_id: str, new_id: str) -> str:
        old = self._require(old_id)
        new = self._require(new_id)
        old_lines = self._semantic_lines(old)
        new_lines = self._semantic_lines(new)
        return "\n".join(difflib.unified_diff(old_lines, new_lines,
            fromfile=f"{old_id}/v{old.version}", tofile=f"{new_id}/v{new.version}", lineterm=""))

    @staticmethod
    def _semantic_lines(card: MemoryCard) -> list[str]:
        return ([f"content: {card.content}"] + [f"precondition: {item}" for item in card.preconditions]
                + [f"procedure: {item}" for item in card.procedure])

    def _require(self, memory_id: str) -> MemoryCard:
        card = self.store.get_card(memory_id)
        if card is None:
            raise KeyError(memory_id)
        return card
