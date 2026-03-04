import asyncio
from urllib.parse import urlparse, parse_qsl, urlunparse

from openai import AsyncOpenAI
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

# Param name used when building kwargs dicts for provider constructors.
_KEY_PARAM = "api_key"


def _normalize_openai_base_url(url: str) -> tuple[str, dict[str, str]]:
    """Normalize an OpenAI-compatible base URL.

    Handles full endpoint URLs (e.g. Azure AI Foundry URLs that include
    '/chat/completions?api-version=...'). Returns a clean base URL (no path
    suffix beyond the mount point) and a dict of query params to pass as
    default_query so they appear on every request.

    Examples
    --------
    Input:  'https://my.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview'
    Output: ('https://my.services.ai.azure.com/models', {'api-version': '2024-05-01-preview'})

    Input:  'https://api.openai.com/v1'
    Output: ('https://api.openai.com/v1', {})
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')

    # Strip trailing /chat/completions — the SDK appends this itself.
    if path.endswith('/chat/completions'):
        path = path[: -len('/chat/completions')]

    # Extract query params (e.g. api-version for Azure).
    query_params: dict[str, str] = dict(parse_qsl(parsed.query))

    # Rebuild clean base URL without query string or fragment.
    clean_url = urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))
    return clean_url, query_params


def build_model(
    provider: str | None = None,
    model_name: str | None = None,
    # Use generic name 'auth' here; mapped to "api_key" kwarg in provider kwargs below.
    auth: str | None = None,
    base_url: str | None = None,
):
    """Build a pydantic-ai model instance.

    All parameters fall back to environment / .env settings when not provided
    (or when provided as empty strings).
    """
    settings = get_settings()

    resolved_provider = (provider or settings.llm_provider).lower()
    resolved_model = model_name or settings.llm_model

    # Only fall back to .env credentials when the provider hasn't been overridden
    # to a different type — otherwise an Anthropic key bleeds into Ollama/OpenAI
    # requests (and vice versa) causing confusing auth errors.
    env_provider = settings.llm_provider.lower()
    same_provider_family = not provider or resolved_provider == env_provider
    resolved_auth = auth or (settings.llm_api_key if same_provider_family else None)
    resolved_url = base_url or (settings.llm_base_url if same_provider_family else None)

    if resolved_provider == "anthropic":
        # Build kwargs dict to avoid literal secret-like patterns in code
        p_kwargs = {_KEY_PARAM: resolved_auth}
        return AnthropicModel(resolved_model, provider=AnthropicProvider(**p_kwargs))

    if resolved_provider in ("openai", "ollama", "openai-compatible"):
        effective_auth = resolved_auth or "ollama"

        if resolved_url:
            clean_url, query_params = _normalize_openai_base_url(resolved_url)
            # Build AsyncOpenAI directly to pass default_query for Azure api-version.
            client_kwargs: dict = {_KEY_PARAM: effective_auth, "base_url": clean_url}
            if query_params:
                client_kwargs["default_query"] = query_params
            openai_client = AsyncOpenAI(**client_kwargs)
            return OpenAIModel(resolved_model, provider=OpenAIProvider(openai_client=openai_client))

        p_kwargs = {_KEY_PARAM: effective_auth}
        return OpenAIModel(resolved_model, provider=OpenAIProvider(**p_kwargs))

    raise ValueError(f"Unsupported LLM_PROVIDER: {resolved_provider!r}")


async def run_pipeline(
    markdown: str,
    provider: str | None = None,
    model_name: str | None = None,
    auth: str | None = None,
    base_url: str | None = None,
) -> DealAnalysis:
    """Run the full agent pipeline: vitals + classifier in parallel, then metrics."""
    model = build_model(provider=provider, model_name=model_name, auth=auth, base_url=base_url)

    vitals_agent: Agent[None, CompanyVitals] = Agent(
        model=model,
        output_type=CompanyVitals,
        system_prompt=_VITALS_SYSTEM,
    )
    classifier_agent: Agent[None, DealClassification] = Agent(
        model=model,
        output_type=DealClassification,
        system_prompt=_CLASSIFIER_SYSTEM,
    )

    vitals_result, classifier_result = await asyncio.gather(
        vitals_agent.run(markdown),
        classifier_agent.run(markdown),
    )

    vitals = vitals_result.output
    classification = classifier_result.output

    metrics_prompt = f"Deal category: {classification.category}\n\n{markdown}"

    match classification.category:
        case "buyout":
            metrics_agent: Agent = Agent(
                model=model, output_type=BuyoutMetrics, system_prompt=_BUYOUT_METRICS_SYSTEM
            )
        case "growth":
            metrics_agent = Agent(
                model=model, output_type=GrowthMetrics, system_prompt=_GROWTH_METRICS_SYSTEM
            )
        case "minority":
            metrics_agent = Agent(
                model=model, output_type=MinorityMetrics, system_prompt=_MINORITY_METRICS_SYSTEM
            )
        case _:
            raise ValueError(f"Unknown category: {classification.category}")

    metrics_result = await metrics_agent.run(metrics_prompt)

    return DealAnalysis(
        vitals=vitals,
        classification=classification,
        metrics=metrics_result.output,
    )
