import json
import asyncio
from fastapi import FastAPI, File, UploadFile
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
async def analyze(files: list[UploadFile] = File(...)):
    async def event_stream():
        try:
            yield _sse({"type": "progress", "step": "extracting", "message": "Extracting documents..."})
            markdown = await extract_uploads_to_markdown(files)

            # Emit all progress steps before the LLM pipeline begins
            yield _sse({"type": "progress", "step": "classifying", "message": "Classifying deal..."})
            await asyncio.sleep(0)
            yield _sse({"type": "progress", "step": "extracting_metrics", "message": "Extracting metrics..."})
            await asyncio.sleep(0)

            result = await run_pipeline(markdown)

            yield _sse({"type": "result", "data": result.model_dump()})

        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
