import json

import pytest

from memory_lab.agent import AutonomousAgent
from memory_lab.environment import DemoProjectEnvironment
from memory_lab.events import EventStore
from memory_lab.memory import NoneMemory
from memory_lab.model_client import DeepSeekModelClient
from memory_lab.scenarios import build_learning_task


class FakeResponse:
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self):
        return json.dumps({"choices": [{"message": {"content":
            '{"tool_name":"run_integration_tests","arguments":{"module":"payments"}}'}}]}).encode()


def test_deepseek_client_builds_request_and_parses_action(monkeypatch):
    captured = {}
    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.data)
        return FakeResponse()
    monkeypatch.setattr("memory_lab.model_client.urlopen", fake_urlopen)
    client = DeepSeekModelClient(api_key="secret", base_url="https://example.test")
    action = client.decide(build_learning_task("learn-1"), ["run_integration_tests(module)"], [], [], [])
    assert action.tool_name == "run_integration_tests"
    assert captured["url"] == "https://example.test/chat/completions"
    assert captured["auth"] == "Bearer secret"
    assert captured["body"]["temperature"] == 0


def test_deepseek_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("memory_lab.model_client.load_dotenv", lambda: None)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        DeepSeekModelClient()


def test_deepseek_agent_reports_online_planner(tmp_path, monkeypatch):
    monkeypatch.setattr("memory_lab.model_client.urlopen", lambda request, timeout: FakeResponse())
    agent = AutonomousAgent(DemoProjectEnvironment(), EventStore(tmp_path / "events.jsonl"),
                            DeepSeekModelClient(api_key="secret"), max_steps=1)
    result = agent.run_task(build_learning_task("learn-1"), NoneMemory(), "learn-1")
    assert result.planner == "deepseek"
