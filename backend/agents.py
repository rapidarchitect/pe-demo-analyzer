import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from backend.config import get_settings
from backend.models import (
    CompanyVitals,
    DealClassification,
    BuyoutMetrics,
    GrowthMetrics,
    MinorityMetrics,
    DealAnalysis,
)

_VITALS_SYSTEM = """You are a financial analyst assistant. Extract basic company profile information
from the provided deal document (CIM, teaser, or financial model). Return only what is explicitly
stated in the document — do not infer or fabricate values."""

_CLASSIFIER_SYSTEM = """You are a private equity deal classification expert. Classify the deal
into exactly one of three categories:
- buyout: acquiring majority/full control of a mature, profitable business
- growth: minority or majority investment in a high-growth, typically loss-making or early-profit company
- minority: taking a minority stake in an established business without control

Base your classification on deal structure, financial profile, and language in the document.
Provide a confidence score (0.0-1.0) and brief reasoning."""

_BUYOUT_METRICS_SYSTEM = """You are a private equity financial analyst. Extract buyout deal metrics
from the document. Return values exactly as they appear (e.g. '42.3M', '~19%').
Return null for any metric not found in the document. Do not estimate or interpolate."""

_GROWTH_METRICS_SYSTEM = """You are a venture/growth equity analyst. Extract growth deal metrics
from the document. Focus on ARR/MRR, growth rates, and retention. Return values exactly as they
appear. Return null for any metric not found. Do not estimate or interpolate."""

_MINORITY_METRICS_SYSTEM = """You are a private equity analyst. Extract minority deal metrics
from the document. Include both SaaS metrics (ARR if applicable) and traditional metrics (EBITDA).
Return values exactly as they appear. Return null for any metric not found."""


def build_model():
    """Build a pydantic-ai model instance from env configuration."""
    settings = get_settings()
    provider = settings.llm_provider.lower()

    # Build kwargs dict to avoid literal secret-like patterns in code
    key_value = settings.llm_api_key
    model_name = settings.llm_model

    if provider == "anthropic":
        p_kwargs = {"api_key": key_value}
        return AnthropicModel(model_name, provider=AnthropicProvider(**p_kwargs))

    if provider in ("openai", "ollama", "openai-compatible"):
        p_kwargs = {"api_key": key_value or "ollama"}
        if settings.llm_base_url:
            p_kwargs["base_url"] = settings.llm_base_url
        return OpenAIModel(model_name, provider=OpenAIProvider(**p_kwargs))

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider!r}")


_model = build_model()

vitals_agent = Agent(
    model=_model,
    output_type=CompanyVitals,
    system_prompt=_VITALS_SYSTEM,
)

classifier_agent = Agent(
    model=_model,
    output_type=DealClassification,
    system_prompt=_CLASSIFIER_SYSTEM,
)

buyout_metrics_agent = Agent(
    model=_model,
    output_type=BuyoutMetrics,
    system_prompt=_BUYOUT_METRICS_SYSTEM,
)

growth_metrics_agent = Agent(
    model=_model,
    output_type=GrowthMetrics,
    system_prompt=_GROWTH_METRICS_SYSTEM,
)

minority_metrics_agent = Agent(
    model=_model,
    output_type=MinorityMetrics,
    system_prompt=_MINORITY_METRICS_SYSTEM,
)


async def run_pipeline(markdown: str) -> DealAnalysis:
    """Run the full agent pipeline: vitals + classifier in parallel, then metrics."""
    vitals_result, classifier_result = await asyncio.gather(
        vitals_agent.run(markdown),
        classifier_agent.run(markdown),
    )

    vitals = vitals_result.output
    classification = classifier_result.output

    metrics_prompt = f"Deal category: {classification.category}\n\n{markdown}"

    match classification.category:
        case "buyout":
            metrics_result = await buyout_metrics_agent.run(metrics_prompt)
        case "growth":
            metrics_result = await growth_metrics_agent.run(metrics_prompt)
        case "minority":
            metrics_result = await minority_metrics_agent.run(metrics_prompt)
        case _:
            raise ValueError(f"Unknown category: {classification.category}")

    return DealAnalysis(
        vitals=vitals,
        classification=classification,
        metrics=metrics_result.output,
    )
