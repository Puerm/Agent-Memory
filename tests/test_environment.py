from memory_lab.environment import DemoProjectEnvironment
from memory_lab.schemas import Action


def test_environment_requires_env_then_fixtures_then_passes() -> None:
    environment = DemoProjectEnvironment()

    assert environment.execute(Action(tool_name="run_integration_tests", arguments={"module": "payments"})).error == "E_ENV_REQUIRED"
    assert environment.execute(Action(tool_name="init_test_data")).error == "E_ENV_REQUIRED"

    assert environment.execute(Action(tool_name="set_env", arguments={"key": "APP_ENV", "value": "test"})).ok
    assert environment.execute(Action(tool_name="run_integration_tests", arguments={"module": "payments"})).error == "E_FIXTURE_REQUIRED"

    assert environment.execute(Action(tool_name="init_test_data")).ok
    result = environment.execute(Action(tool_name="run_integration_tests", arguments={"module": "payments"}))
    assert result.ok and result.task_complete


def test_force_is_always_rejected() -> None:
    result = DemoProjectEnvironment().execute(
        Action(tool_name="run_integration_tests", arguments={"module": "payments", "force": True})
    )
    assert result.error == "UNSAFE_ACTION_REJECTED"
