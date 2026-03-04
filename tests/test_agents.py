import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.models import (
    CompanyVitals, DealClassification, BuyoutMetrics,
    GrowthMetrics, MinorityMetrics, DealAnalysis
)


def test_build_model_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-test")
    monkeypatch.setenv("LLM_BASE_URL", "")
    # Reimport after env change
    import importlib
    import backend.config
    importlib.reload(backend.config)
    from backend.agents import build_model
    model = build_model()
    assert model is not None


def test_build_model_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_BASE_URL", "")
    import importlib
    import backend.config
    importlib.reload(backend.config)
    from backend.agents import build_model
    model = build_model()
    assert model is not None


def test_normalize_openai_base_url_strips_chat_completions():
    """Full Azure AI Foundry URL should be normalised to a clean base + query params."""
    from backend.agents import _normalize_openai_base_url

    url = "https://my-resource.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview"
    clean, params = _normalize_openai_base_url(url)

    assert clean == "https://my-resource.services.ai.azure.com/models"
    assert params == {"api-version": "2024-05-01-preview"}


def test_normalize_openai_base_url_plain():
    """A plain base URL without path suffix should be returned unchanged."""
    from backend.agents import _normalize_openai_base_url

    url = "https://api.openai.com/v1"
    clean, params = _normalize_openai_base_url(url)

    assert clean == "https://api.openai.com/v1"
    assert params == {}


@pytest.mark.asyncio
async def test_run_pipeline_returns_deal_analysis():
    """Test pipeline using mocks to avoid real LLM calls."""
    from pydantic_ai import Agent
    from backend.agents import run_pipeline

    vitals_mock = CompanyVitals(name="TestCo", geography="France")
    classification_mock = DealClassification(
        category="buyout", confidence=0.88, reasoning="Mature profitable business"
    )
    metrics_mock = BuyoutMetrics(revenue="€42M", ebitda="€8M")

    # Agents are now created inside run_pipeline; patch at the class level.
    # asyncio.gather runs vitals then classifier first (both listed in order),
    # then metrics — so the side_effect list matches that order.
    responses = [
        MagicMock(output=vitals_mock),
        MagicMock(output=classification_mock),
        MagicMock(output=metrics_mock),
    ]

    with patch("backend.agents.build_model", return_value=MagicMock()), \
         patch.object(Agent, "run", AsyncMock(side_effect=responses)):
        result = await run_pipeline("Some deal markdown text")

    assert isinstance(result, DealAnalysis)
    assert result.vitals.name == "TestCo"
    assert result.classification.category == "buyout"
    assert isinstance(result.metrics, BuyoutMetrics)
    assert result.metrics.revenue == "€42M"
