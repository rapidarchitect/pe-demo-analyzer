# PE Deal Analyzer — Project Memory

## Project Overview

AI-powered private equity deal analyzer. Uploads CIM/teaser docs → extracts text → classifies deal type → streams structured financial metrics via SSE.

**Stack**: FastAPI (backend) + SvelteKit (frontend) + pydantic-ai agents + markitdown/pymupdf4llm extraction

**One-liner**: "AI-powered private equity deal analyzer that extracts, classifies, and streams structured financial metrics from CIMs and teasers."

---

## Key Files

| Path             | Purpose                           |
| ---------------- | --------------------------------- |
| `backend/`       | FastAPI app, agents, extraction   |
| `frontend/`      | SvelteKit UI                      |
| `main.py`        | Entry point                       |
| `pyproject.toml` | Python deps (uv)                  |
| `demo.gif`       | Demo screencast (added to README) |

---

## Sessions

### 2026-03-03

**Accomplished:**

- Added `demo.gif` to `README.md` (below description, above first section divider)
- Provided one-line GitHub repo description
- Wrote comprehensive `.gitignore` (Python, env, Claude/.mcp/.serena/.playwright-mcp, macOS, frontend)

**State**: Project is clean and ready for GitHub push.
