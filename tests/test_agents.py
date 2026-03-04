import pytest
import os
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


@pytest.mark.asyncio
async def test_run_pipeline_returns_deal_analysis(monkeypatch):
    """Test pipeline with pydantic-ai TestModel to avoid real LLM calls."""
    from pydantic_ai.models.test import TestModel
    from backend.agents import run_pipeline

    # Patch the agents to use TestModel
    vitals_mock = CompanyVitals(name="TestCo", geography="France")
    classification_mock = DealClassification(
        category="buyout", confidence=0.88, reasoning="Mature profitable business"
    )
    metrics_mock = BuyoutMetrics(revenue="€42M", ebitda="€8M")

    with patch("backend.agents.vitals_agent") as mock_v, \
         patch("backend.agents.classifier_agent") as mock_c, \
         patch("backend.agents.buyout_metrics_agent") as mock_m:

        mock_v.run = AsyncMock(return_value=MagicMock(output=vitals_mock))
        mock_c.run = AsyncMock(return_value=MagicMock(output=classification_mock))
        mock_m.run = AsyncMock(return_value=MagicMock(output=metrics_mock))

        result = await run_pipeline("Some deal markdown text")

    assert isinstance(result, DealAnalysis)
    assert result.vitals.name == "TestCo"
    assert result.classification.category == "buyout"
    assert isinstance(result.metrics, BuyoutMetrics)
    assert result.metrics.revenue == "€42M"
