import tempfile
import os
from pathlib import Path
from markitdown import MarkItDown

MIN_CHAR_THRESHOLD = 200


def extract_to_markdown(file_path: str) -> str:
    """Convert a single file to markdown via markitdown.
    Falls back to pymupdf4llm for PDFs that yield too little text.
    """
    md = MarkItDown()
    result = md.convert(file_path)
    text = result.text_content or ""

    # Fallback for scanned/image-based PDFs
    if file_path.lower().endswith(".pdf") and len(text.strip()) < MIN_CHAR_THRESHOLD:
        text = _pymupdf_fallback(file_path)

    return text


def _pymupdf_fallback(file_path: str) -> str:
    """Extract PDF text using pymupdf4llm (handles scanned docs)."""
    import pymupdf4llm
    return pymupdf4llm.to_markdown(file_path)


def extract_files_to_markdown(file_paths: list[str]) -> str:
    """Extract and concatenate multiple files into a single markdown string."""
    parts = []
    for path in file_paths:
        text = extract_to_markdown(path)
        if text.strip():
            filename = Path(path).name
            parts.append(f"## Source: {filename}\n\n{text.strip()}")
    return "\n\n---\n\n".join(parts)


async def extract_uploads_to_markdown(files: list) -> str:
    """Accept FastAPI UploadFile objects, save to temp, extract, clean up."""
    temp_paths = []
    try:
        for upload in files:
            suffix = Path(upload.filename or "file").suffix or ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await upload.read()
                tmp.write(content)
                temp_paths.append(tmp.name)
        return extract_files_to_markdown(temp_paths)
    finally:
        for path in temp_paths:
            try:
                os.unlink(path)
            except OSError:
                pass
