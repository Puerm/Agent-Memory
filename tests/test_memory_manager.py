from datetime import datetime, timezone

from memory_lab.memory.manager import MemoryManager
from memory_lab.memory.store import MemoryStore
from memory_lab.schemas import MemoryCard


def card(memory_id: str = "mem-001") -> MemoryCard:
    now = datetime.now(timezone.utc)
    return MemoryCard(
        memory_id=memory_id,
        memory_type="procedural",
        title="workflow",
        content="set environment then run integration tests",
        procedure=["set_env(APP_ENV, test)", "run_integration_tests(module)"],
        project_id="demo-project",
        source_kind="verified_tool_trajectory",
        source_id="run-001",
        confidence=0.95,
        trust_level="verified",
        risk_level="low",
        valid_from=now,
        created_at=now,
        updated_at=now,
    )


def test_manager_deduplicates_and_can_invalidate(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    manager = MemoryManager(store)

    assert manager.add_or_patch(card()).operation == "ADD"
    assert manager.add_or_patch(card("mem-002")).operation == "NOOP"
    assert len(store.list_cards()) == 1

    revoked = manager.invalidate("mem-001")
    assert revoked.status == "revoked"
    assert store.get_card("mem-001").status == "revoked"
