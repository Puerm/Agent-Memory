"""Structured retrieval with visible hard filters and utility re-ranking."""

from __future__ import annotations

from datetime import datetime, timezone
import re

from ..schemas import AdmissionDecision, MemoryCard, MemoryRetrieval, TaskContext, TrajectoryStep
from .base import MemorySystem
from .embeddings import similarity
from .manager import MemoryManager
from .store import MemoryStore
from .writer import DeterministicWriter


class GovernedMemory(MemorySystem):
    mode = "governed"

    def __init__(self, store: MemoryStore, top_k: int = 3) -> None:
        self.store = store
        self.top_k = top_k
        self.manager = MemoryManager(store)
        self.writer = DeterministicWriter(store, self.manager)
        self._last_admitted_ids: list[str] = []

    def query(self, task: TaskContext) -> MemoryRetrieval:
        candidates: list[tuple[MemoryCard, AdmissionDecision]] = []
        now = task.current_time
        for card in self.store.list_cards():
            semantic = similarity(task.task_text, self._search_text(card))
            reasons: list[str] = []
            if card.status != "active":
                reasons.append("INACTIVE")
            if card.release_status not in {"canary", "active"}:
                reasons.append("NOT_RELEASED")
            if card.valid_from > now or (card.valid_to is not None and now >= card.valid_to):
                reasons.append("EXPIRED")
            if card.project_id is not None and card.project_id != task.project_id:
                reasons.append("SCOPE_MISMATCH")
            if card.trust_level == "untrusted":
                reasons.append("UNTRUSTED_SOURCE")
            if card.risk_level == "high":
                reasons.append("RISK_TOO_HIGH")
            if card.confidence < 0.5:
                reasons.append("LOW_CONFIDENCE")
            if not self._required_tools(card).issubset(set(task.allowed_tools)):
                reasons.append("TOOL_NOT_ALLOWED")
            if semantic <= 0.0:
                reasons.append("NOT_TASK_RELEVANT")
            if reasons:
                decision = AdmissionDecision(
                    memory_id=card.memory_id,
                    admitted=False,
                    semantic_score=semantic,
                    reason_codes=reasons,
                )
            else:
                final_score = self._final_score(card, semantic, now)
                decision = AdmissionDecision(
                    memory_id=card.memory_id,
                    admitted=True,
                    semantic_score=semantic,
                    final_score=final_score,
                    reason_codes=["SCOPE_MATCH", f"{card.trust_level.upper()}_SOURCE"],
                )
            candidates.append((card, decision))

        candidates.sort(
            key=lambda item: (
                item[1].admitted,
                item[1].final_score if item[1].final_score is not None else item[1].semantic_score,
            ),
            reverse=True,
        )
        admitted = [(card, decision) for card, decision in candidates if decision.admitted][: self.top_k]
        cards = [card for card, _ in admitted]
        decisions = [decision for _, decision in candidates]
        self._last_admitted_ids = [card.memory_id for card in cards]
        return MemoryRetrieval(cards=cards, decisions=decisions)

    def observe(self, task: TaskContext, trajectory: list[TrajectoryStep], trajectory_id: str) -> None:
        self.writer.extract_and_store(task, trajectory, trajectory_id)
        succeeded = any(step.result.task_complete for step in trajectory)
        for memory_id in self._last_admitted_ids:
            card = self.store.get_card(memory_id)
            if card is None:
                continue
            card.use_count += 1
            card.last_used_at = datetime.now(timezone.utc)
            if succeeded:
                card.success_count += 1
            else:
                card.failure_count += 1
            card.updated_at = card.last_used_at
            self.store.put_card(card)
        self._last_admitted_ids = []

    @staticmethod
    def _search_text(card: MemoryCard) -> str:
        return " ".join([card.title, card.content, *card.problem_signature, *card.procedure])

    @staticmethod
    def _required_tools(card: MemoryCard) -> set[str]:
        return {
            match.group(1)
            for step in card.procedure
            if (match := re.match(r"\s*([a-z_]+)\(", step)) is not None
        }

    @staticmethod
    def _final_score(card: MemoryCard, semantic: float, now: datetime) -> float:
        task_utility = 1.0 if "run_integration_tests" in " ".join(card.procedure) else 0.4
        source_trust = {"verified": 1.0, "trusted": 0.7, "untrusted": 0.0}[card.trust_level]
        total_uses = card.success_count + card.failure_count
        historical_success = card.success_count / total_uses if total_uses else 1.0
        age_days = max(0.0, (now - card.updated_at).total_seconds() / 86400)
        recency = max(0.0, 1.0 - age_days / 365)
        return round(
            0.40 * semantic
            + 0.20 * task_utility
            + 0.15 * card.confidence
            + 0.10 * source_trust
            + 0.10 * historical_success
            + 0.05 * recency,
            4,
        )
