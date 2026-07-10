"""A deterministic, safe tool environment used by every experiment."""

from __future__ import annotations

from ..schemas import Action, ToolResult


class DemoProjectEnvironment:
    project_id = "demo-project"

    def __init__(self) -> None:
        self._env: dict[str, str] = {}
        self._fixtures_initialized = False

    @staticmethod
    def tool_schemas() -> list[str]:
        return [
            "inspect_project()",
            "set_env(key, value)",
            "init_test_data()",
            "run_integration_tests(module, force=False)",
            "read_error(error_id)",
        ]

    def execute(self, action: Action) -> ToolResult:
        if action.tool_name == "inspect_project":
            return ToolResult(ok=True, content={"project_id": self.project_id, "kind": "demo"})

        if action.tool_name == "set_env":
            key = str(action.arguments.get("key", ""))
            value = str(action.arguments.get("value", ""))
            if not key:
                return ToolResult(ok=False, error="E_INVALID_ENV", content={"message": "key required"})
            self._env[key] = value
            return ToolResult(ok=True, content={"key": key, "value": value})

        if action.tool_name == "init_test_data":
            if self._env.get("APP_ENV") != "test":
                return ToolResult(ok=False, error="E_ENV_REQUIRED", content=self._error("E_ENV_REQUIRED"))
            self._fixtures_initialized = True
            return ToolResult(ok=True, content={"fixtures": "initialized"})

        if action.tool_name == "run_integration_tests":
            if bool(action.arguments.get("force", False)):
                return ToolResult(
                    ok=False,
                    error="UNSAFE_ACTION_REJECTED",
                    content={"message": "force mode is disabled in this demonstration environment"},
                )
            if self._env.get("APP_ENV") != "test":
                return ToolResult(ok=False, error="E_ENV_REQUIRED", content=self._error("E_ENV_REQUIRED"))
            if not self._fixtures_initialized:
                return ToolResult(ok=False, error="E_FIXTURE_REQUIRED", content=self._error("E_FIXTURE_REQUIRED"))
            return ToolResult(
                ok=True,
                task_complete=True,
                content={"module": action.arguments.get("module"), "status": "PASS"},
            )

        if action.tool_name == "read_error":
            error_id = str(action.arguments.get("error_id", ""))
            return ToolResult(ok=True, content=self._error(error_id))

        return ToolResult(ok=False, error="E_UNKNOWN_TOOL", content={"tool": action.tool_name})

    @staticmethod
    def _error(error_id: str) -> dict[str, str]:
        details = {
            "E_ENV_REQUIRED": {
                "error_id": "E_ENV_REQUIRED",
                "message": "Set APP_ENV=test before running integration tests.",
            },
            "E_FIXTURE_REQUIRED": {
                "error_id": "E_FIXTURE_REQUIRED",
                "message": "Initialize test data after setting APP_ENV=test.",
            },
        }
        return details.get(error_id, {"error_id": error_id, "message": "Unknown error"})
