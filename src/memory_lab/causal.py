"""Counterfactual replay for memory-level blame attribution."""

from .agent import AutonomousAgent
from .environment import DemoProjectEnvironment
from .events import EventStore
from .memory import GovernedMemory, NoneMemory
from .memory.base import MemorySystem
from .model_client import RuleBasedModelClient
from .schemas import AdmissionDecision, CausalAttribution, MemoryRetrieval, TaskContext


class FixedMemory(MemorySystem):
    """Replay adapter that injects exactly one version without mutating memory state."""
    mode = "governed"

    def __init__(self, card) -> None:
        self.card = card

    def query(self, task):
        return MemoryRetrieval(cards=[self.card], decisions=[AdmissionDecision(
            memory_id=self.card.memory_id, admitted=True, semantic_score=1.0,
            final_score=1.0, reason_codes=["CAUSAL_REPLAY_FIXED_VERSION"])])

    def observe(self, task, trajectory, trajectory_id):
        return None


def replay_memory_effect(task: TaskContext, scenario: str, store, event_path,
                         memory_id: str | None = None, baseline_id: str | None = None) -> list[CausalAttribution]:
    """Compare the observed governed run with a no-memory replay on fresh environments."""
    model = RuleBasedModelClient()
    observed_memory = FixedMemory(store.get_card(memory_id)) if memory_id else GovernedMemory(store)
    if memory_id and observed_memory.card is None:
        raise KeyError(memory_id)
    observed = AutonomousAgent(DemoProjectEnvironment(), EventStore(event_path), model).run_task(
        task.model_copy(update={"session_id": task.session_id + "-with"}), observed_memory, scenario)
    baseline_memory = NoneMemory()
    if baseline_id:
        baseline_card = store.get_card(baseline_id)
        if baseline_card is None:
            raise KeyError(baseline_id)
        baseline_memory = FixedMemory(baseline_card)
    counterfactual = AutonomousAgent(DemoProjectEnvironment(), EventStore(event_path), model).run_task(
        task.model_copy(update={"session_id": task.session_id + "-without"}), baseline_memory, scenario)
    delta = counterfactual.failed_tool_calls - observed.failed_tool_calls
    return [CausalAttribution(memory_id=memory_id, observed_success=observed.success,
        counterfactual_success=counterfactual.success, observed_failures=observed.failed_tool_calls,
        counterfactual_failures=counterfactual.failed_tool_calls,
        helpful_contribution=max(0.0, min(1.0, delta / 2)),
        harmful_contribution=max(0.0, min(1.0, -delta / 2))) for memory_id in observed.admitted_memory_ids]
