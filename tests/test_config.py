from memory_lab.config import load_dotenv


def test_load_dotenv_reads_quotes_and_preserves_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY='from-file'\nDEEPSEEK_MODEL=deepseek-chat\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-environment")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    assert load_dotenv(env_file) == env_file
    import os
    assert os.environ["DEEPSEEK_API_KEY"] == "from-environment"
    assert os.environ["DEEPSEEK_MODEL"] == "deepseek-chat"
