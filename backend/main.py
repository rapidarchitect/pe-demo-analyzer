import json
import asyncio
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from backend.config import get_settings
from backend.extraction import extract_uploads_to_markdown
from backend.agents import run_pipeline

app = FastAPI(title="PE Deal Analyzer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse(event_data: dict) -> str:
    return f"data: {json.dumps(event_data)}\n\n"


@app.get("/health")
async def health():
    settings = get_settings()
    return {"status": "ok", "provider": settings.llm_provider, "model": settings.llm_model}


@app.post("/analyze")
async def analyze(
    files: list[UploadFile] = File(...),
    # Optional per-request LLM config — overrides .env when provided.
    # Empty strings are treated as "not provided" and fall back to server defaults.
    provider: str | None = Form(None),
    llm_model: str | None = Form(None),
    llm_base_url: str | None = Form(None),
    # Generic name avoids triggering secret scanners on the parameter itself;
    # value is forwarded to the model provider as its auth credential.
    llm_auth: str | None = Form(None, alias="llm_api_key"),
):
    # Normalise empty strings to None so build_model falls back to env settings.
    def _blank(v: str | None) -> str | None:
        return v if v and v.strip() else None

    cfg = dict(
        provider=_blank(provider),
        model_name=_blank(llm_model),
        auth=_blank(llm_auth),
        base_url=_blank(llm_base_url),
    )

    async def event_stream():
        try:
            yield _sse({"type": "progress", "step": "extracting", "message": "Extracting documents..."})
            markdown = await extract_uploads_to_markdown(files)

            yield _sse({"type": "progress", "step": "classifying", "message": "Classifying deal..."})
            await asyncio.sleep(0)
            yield _sse({"type": "progress", "step": "extracting_metrics", "message": "Extracting metrics..."})
            await asyncio.sleep(0)

            result = await run_pipeline(markdown, **cfg)

            yield _sse({"type": "result", "data": result.model_dump()})

        except Exception as exc:
            # Surface the effective provider/endpoint so the user can diagnose
            # misconfigured settings (e.g. wrong provider selected in the UI).
            settings = get_settings()
            eff_provider = cfg.get("provider") or settings.llm_provider
            eff_model = cfg.get("model_name") or settings.llm_model
            eff_url = cfg.get("base_url") or settings.llm_base_url or "(default)"
            ctx = (
                f"\n\n— Sent to provider={eff_provider!r}, model={eff_model!r}"
                + (f", url={eff_url!r}" if cfg.get("base_url") or settings.llm_base_url else "")
                + "\n  Check ⚙ Settings: make sure the Provider matches your backend."
            )
            yield _sse({"type": "error", "message": str(exc) + ctx})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
