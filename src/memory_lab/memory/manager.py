"""Lifecycle manager for ADD, PATCH, INVALIDATE and NOOP decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
