from memory_lab.agent import AutonomousAgent
from memory_lab.causal import replay_memory_effect
from memory_lab.environment import DemoProjectEnvironment
from memory_lab.events import EventStore
from memory_lab.memory import GovernedMemory, NoneMemory
from memory_lab.memory.manager import MemoryManager
from memory_lab.memory.store import MemoryStore
from memory_lab.model_client import RuleBasedModelClient
from memory_lab.scenarios import build_learning_task


def run(tmp_path, memory, scenario):
    return AutonomousAgent(DemoProjectEnvironment(), EventStore(tmp_path / "events.jsonl"),
                           RuleBasedModelClient()).run_task(build_learning_task(scenario), memory, scenario)


def test_autonomous_agent_learns_across_fresh_sessions(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    first = run(tmp_path, GovernedMemory(store), "learn-1")
    second = run(tmp_path, GovernedMemory(store), "learn-2")
    control = run(tmp_path, NoneMemory(), "learn-2")
    assert first.planner == "autonomous" and first.failed_tool_calls == 2
    assert second.success and second.failed_tool_calls == 0 and second.tool_calls == 3
    assert control.success and control.failed_tool_calls == 2 and control.tool_calls == 7
    assert first.session_id != second.session_id


def test_counterfactual_blame_measures_helpful_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    run(tmp_path, GovernedMemory(store), "learn-1")
    rows = replay_memory_effect(build_learning_task("learn-2"), "learn-2", store, tmp_path / "replay.jsonl")
    assert rows[0].memory_id == "mem-001"
    assert rows[0].helpful_contribution == 1.0
    assert rows[0].harmful_contribution == 0.0


def test_release_state_machine_and_rollback(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    run(tmp_path, GovernedMemory(store), "learn-1")
    card = store.get_card("mem-001")
    candidate = card.model_copy(update={"memory_id": "mem-002", "version": 2,
        "supersedes": "mem-001", "release_status": "candidate"})
    store.put_card(candidate)
    manager = MemoryManager(store)
    manager.promote("mem-002", "tested")
    manager.promote("mem-002", "canary")
    manager.promote("mem-002", "active")
    restored = manager.rollback("mem-002")
    assert restored.memory_id == "mem-001" and restored.release_status == "active"
    assert store.get_card("mem-002").status == "revoked"


def test_consolidation_regresses_diff_and_rollback_restores_behavior(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    run(tmp_path, GovernedMemory(store), "learn-1")
    manager = MemoryManager(store)
    v2 = manager.consolidate("mem-001")

    regressed = run(tmp_path, GovernedMemory(store), "learn-2")
    rendered = manager.diff("mem-001", v2.memory_id)
    assert v2.memory_id == "mem-002" and v2.supersedes == "mem-001"
    assert regressed.success and regressed.failed_tool_calls == 1
    assert "-procedure: set_env(APP_ENV, test)" in rendered
    assert "+procedure: set_env(ENV, test)" in rendered

    restored = manager.rollback("mem-002")
    recovered = run(tmp_path, GovernedMemory(store), "learn-2")
    assert restored.memory_id == "mem-001"
    assert recovered.success and recovered.failed_tool_calls == 0

    harmful = replay_memory_effect(build_learning_task("learn-2"), "learn-2", store,
        tmp_path / "version-replay.jsonl", memory_id="mem-002", baseline_id="mem-001")
    assert harmful[0].harmful_contribution == 0.5
    assert harmful[0].observed_failures == 1
    assert harmful[0].counterfactual_failures == 0
