from memory_lab.agent import DemoAgent
from memory_lab.environment import DemoProjectEnvironment
from memory_lab.events import EventStore
from memory_lab.memory import GovernedMemory, NaiveMemory, NoneMemory
from memory_lab.memory.store import MemoryStore
from memory_lab.scenarios import build_learning_task, inject_unsafe_memory


def execute(tmp_path, memory, scenario: str):
    agent = DemoAgent(DemoProjectEnvironment(), EventStore(tmp_path / "events.jsonl"))
    return agent.run_task(build_learning_task(scenario), memory, scenario)


def test_new_session_governed_memory_eliminates_known_failures(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    first = execute(tmp_path, GovernedMemory(store), "learn-1")
    second = execute(tmp_path, GovernedMemory(store), "learn-2")
    control = execute(tmp_path, NoneMemory(), "learn-2")

    assert first.success and first.failed_tool_calls == 2
    assert second.success and second.failed_tool_calls == 0
    assert second.admitted_memory_ids == ["mem-001"]
    assert control.success and control.failed_tool_calls == 2
    assert first.session_id != second.session_id


def test_naive_raw_memory_can_replay_a_workflow_without_governance(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    execute(tmp_path, NaiveMemory(store), "learn-1")
    result = execute(tmp_path, NaiveMemory(store), "learn-2")
    assert result.success
    assert result.failed_tool_calls == 0


def test_injection_enters_naive_context_but_is_rejected_before_governed_prompt(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    execute(tmp_path, GovernedMemory(store), "learn-1")
    inject_unsafe_memory(store)

    naive_result = execute(tmp_path, NaiveMemory(store), "injection")
    governed_result = execute(tmp_path, GovernedMemory(store), "injection")

    assert naive_result.errors == ["UNSAFE_ACTION_REJECTED"]
    assert not naive_result.success
    assert governed_result.success and governed_result.failed_tool_calls == 0
    unsafe = next(item for item in governed_result.decisions if item.memory_id == "mem-666")
    assert not unsafe.admitted
    assert "SCOPE_MISMATCH" in unsafe.reason_codes
    assert "UNTRUSTED_SOURCE" in unsafe.reason_codes
    assert "RISK_TOO_HIGH" in unsafe.reason_codes
