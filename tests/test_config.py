import os
import pytest
from backend.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_BASE_URL", "")
    s = Settings()
    assert s.llm_provider == "openai"
    assert s.llm_model == "gpt-4o"
    assert s.llm_api_key == "sk-test"
    assert s.llm_base_url == ""


def test_settings_valid_providers(monkeypatch):
    for provider in ["anthropic", "openai", "ollama", "openai-compatible"]:
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv("LLM_MODEL", "some-model")
        monkeypatch.setenv("LLM_API_KEY", "key")
        s = Settings()
        assert s.llm_provider == provider
