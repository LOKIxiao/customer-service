from app.llm.factory import create_llm_client
from app.llm.fake_client import FakeLLMClient


def test_create_llm_client_uses_fake_client_by_default(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")

    client = create_llm_client()

    assert isinstance(client, FakeLLMClient)


def test_create_llm_client_uses_fake_client_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")

    client = create_llm_client()

    assert isinstance(client, FakeLLMClient)
