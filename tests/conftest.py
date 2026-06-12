import pytest


@pytest.fixture(autouse=True)
def disable_langsmith_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
