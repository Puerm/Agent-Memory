from datetime import datetime, timedelta, timezone

from memory_lab.memory.governed import GovernedMemory
from memory_lab.memory.store import MemoryStore
from memory_lab.schemas import MemoryCard, TaskContext


def make_card(memory_id: str, **overrides) -> MemoryCard:
    now = datetime.now(timezone.utc)
    values = {
        "memory_id": memory_id,
        "memory_type": "procedural",
        "title": "integration workflow",
        "content": "Run integration tests after setting APP_ENV test and initializing fixtures.",
        "procedure": ["set_env(APP_ENV, test)", "init_test_data()", "run_integration_tests(module)"],
        "project_id": "demo-project",
        "source_kind": "verified_tool_trajectory",
        "source_id": "run-001",
        "confidence": 0.95,
        "trust_level": "verified",
        "risk_level": "low",
        "valid_from": now - timedelta(minutes=1),
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return MemoryCard(**values)


def task() -> TaskContext:
    return TaskContext(
        task_id="task-1",
        task_text="Run integration tests for the orders module.",
        project_id="demo-project",
        session_id="fresh-session",
    )


def test_governed_admits_verified_matching_memory(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.put_card(make_card("mem-good"))

    retrieval = GovernedMemory(store).query(task())
    assert [card.memory_id for card in retrieval.cards] == ["mem-good"]
    assert retrieval.decisions[0].admitted
    assert "SCOPE_MATCH" in retrieval.decisions[0].reason_codes


def test_governed_rejects_expired_scope_mismatch_and_unsafe_source(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    now = datetime.now(timezone.utc)
    store.put_card(make_card("mem-expired", valid_to=now - timedelta(seconds=1)))
    store.put_card(
        make_card(
            "mem-unsafe",
            project_id="another-project",
            source_kind="untrusted_issue_comment",
            trust_level="untrusted",
            risk_level="high",
            confidence=0.30,
        )
    )

    decisions = {item.memory_id: item for item in GovernedMemory(store).query(task()).decisions}
    assert "EXPIRED" in decisions["mem-expired"].reason_codes
    assert not decisions["mem-unsafe"].admitted
    assert {"SCOPE_MISMATCH", "UNTRUSTED_SOURCE", "RISK_TOO_HIGH", "LOW_CONFIDENCE"}.issubset(
        decisions["mem-unsafe"].reason_codes
    )
