# PE Deal Analyzer

A stateless AI-powered deal sourcing tool for private equity professionals. Upload a CIM, teaser, or financial model and receive structured deal classification, company vitals, and key financial metrics — streamed in real time.

---

## What it does

1. **Extracts** text from uploaded documents (PDF, DOCX, XLSX, PPTX, TXT)
2. **Classifies** the deal as **buyout**, **growth equity**, or **minority stake**
3. **Extracts** category-specific financial metrics (revenue, EBITDA, ARR, leverage, etc.)
4. **Streams** progress and results back to the browser via Server-Sent Events

Three parallel LLM agents run the analysis: a company vitals agent and a classifier run concurrently, then a category-specific metrics agent runs once the deal type is known.

---

## Architecture

```
Browser (SvelteKit)
  │  POST /analyze  multipart/form-data
  │  ← SSE stream (progress + result)
  ▼
FastAPI  (/analyze, /health)
  ├── extraction.py     markitdown → markdown text
  │                     pymupdf4llm fallback for scanned PDFs
  └── agents.py         pydantic-ai agents
        ├── vitals_agent       → CompanyVitals
        ├── classifier_agent   → DealClassification  (parallel)
        └── metrics_agent      → BuyoutMetrics | GrowthMetrics | MinorityMetrics
```

**Backend:** Python 3.12, FastAPI, pydantic-ai, markitdown, pymupdf4llm
**Frontend:** SvelteKit 2 + Svelte 5, Tailwind CSS
**Package manager:** uv (Python), npm (Node)

---

## Requirements

- Python 3.12+
- Node.js 20.19+ or 22.12+ (22.9 works with `--engine-strict false`)
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- An LLM API key (Anthropic, OpenAI, Ollama, or any OpenAI-compatible endpoint)

---

## Quick start

### 1. Clone and install

```bash
git clone <repo-url>
cd pe_deal_analysis

# Python deps
uv sync

# Node deps
npm install --prefix frontend --engine-strict false
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
LLM_PROVIDER=anthropic          # anthropic | openai | ollama | openai-compatible
LLM_MODEL=claude-sonnet-4-6     # model name for chosen provider
LLM_API_KEY=sk-ant-...          # API key (leave blank for ollama)
LLM_BASE_URL=                   # required only for ollama / openai-compatible
```

### 3. Run

**Backend** (terminal 1):

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

**Frontend** (terminal 2):

```bash
npm --prefix frontend run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Using the app

1. Drop one or more files onto the upload zone (or click to browse)
2. Click **Analyze Deal**
3. Watch the progress indicator as the agents work through extraction → classification → metrics
4. Review the results: company vitals card, deal type badge with confidence score, and a metrics table tailored to the deal category
5. Click **Copy JSON** to copy the full structured output, or **Analyze Another Deal** to reset

---

## Supported file types

| Format  | Notes                                                                       |
| ------- | --------------------------------------------------------------------------- |
| `.pdf`  | Text-based PDFs via markitdown; scanned/image PDFs fall back to pymupdf4llm |
| `.docx` | Word documents                                                              |
| `.xlsx` | Excel workbooks                                                             |
| `.pptx` | PowerPoint presentations                                                    |
| `.txt`  | Plain text                                                                  |

Multiple files can be uploaded simultaneously — they are extracted and concatenated before analysis.

---

## LLM provider configuration

| Provider         | `LLM_PROVIDER`      | `LLM_BASE_URL`              |
| ---------------- | ------------------- | --------------------------- |
| Anthropic        | `anthropic`         | —                           |
| OpenAI           | `openai`            | —                           |
| Ollama (local)   | `ollama`            | `http://localhost:11434/v1` |
| LM Studio / vLLM | `openai-compatible` | your endpoint URL           |

For Ollama, `LLM_API_KEY` can be left blank (the backend substitutes `"ollama"`).

---

## Project structure

```
pe_deal_analysis/
├── backend/
│   ├── config.py        # pydantic-settings env loader
│   ├── models.py        # Pydantic schemas (CompanyVitals, DealClassification, metrics)
│   ├── extraction.py    # Document-to-markdown pipeline
│   ├── agents.py        # pydantic-ai agents + run_pipeline()
│   └── main.py          # FastAPI app — /health and /analyze (SSE)
├── frontend/
│   └── src/
│       ├── lib/
│       │   ├── types.ts                  # TypeScript interfaces mirroring backend models
│       │   ├── Dropzone.svelte           # Drag-and-drop file upload
│       │   ├── AnalysisProgress.svelte   # Step-by-step progress indicator
│       │   ├── VitalsCard.svelte         # Company profile card
│       │   ├── ClassificationBadge.svelte # Deal type + confidence display
│       │   └── MetricsTable.svelte       # Category-specific metrics table
│       └── routes/
│           └── +page.svelte              # Main page state machine
├── tests/
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_extraction.py
│   ├── test_agents.py
│   └── test_main.py
├── examples/
│   ├── buyout_teaser_acme_precision.txt    # Leveraged buyout — German manufacturer
│   ├── growth_equity_teaser_synthai.txt    # Series B — UK SaaS company
│   └── minority_stake_nordic_clinics.txt   # Minority stake — Nordic healthcare group
├── pyproject.toml
└── .env.example
```

---

## Data models

### Output structure

```json
{
  "vitals": {
    "name": "Acme Precision Components GmbH",
    "industry": "Precision Engineering",
    "sector": "Automotive & Industrial Components",
    "geography": "Germany",
    "founding_year": 1987,
    "description": "High-tolerance hydraulic and pneumatic component manufacturer"
  },
  "classification": {
    "category": "buyout",
    "confidence": 0.96,
    "reasoning": "Majority stake acquisition of mature, profitable manufacturer with LBO financing structure and management rollover"
  },
  "metrics": {
    "revenue": "€87.4M",
    "ebitda": "€19.3M",
    "ebitda_margin": "22.1%",
    "revenue_growth_rate": "+8.3% YoY",
    "net_debt": "€11.2M",
    "leverage_ratio": "0.58x"
  }
}
```

### Deal categories and their metrics

**Buyout:** revenue, EBITDA, EBITDA margin, revenue growth, net debt, leverage ratio

**Growth equity:** revenue, ARR, MRR, revenue growth, gross margin, net revenue retention, debt levels

**Minority:** revenue, EBITDA, ARR, revenue growth, EBITDA margin, gross margin, debt levels

All metric values are returned as strings exactly as they appear in the source document. Missing metrics are returned as `null`.

---

## SSE event stream

The `/analyze` endpoint streams Server-Sent Events in this sequence:

```
data: {"type": "progress", "step": "extracting", "message": "Extracting documents..."}

data: {"type": "progress", "step": "classifying", "message": "Classifying deal..."}

data: {"type": "progress", "step": "extracting_metrics", "message": "Extracting metrics..."}

data: {"type": "result", "data": { ...DealAnalysis... }}
```

On error:

```
data: {"type": "error", "message": "..."}
```

---

## Running tests

```bash
uv run pytest tests/ -v
```

Expected output: **18 tests, all passing.** Tests use mocked LLM agents — no API calls are made.

```
tests/test_config.py          2 passed
tests/test_models.py          7 passed
tests/test_extraction.py      4 passed
tests/test_agents.py          3 passed
tests/test_main.py            2 passed
```

---

## Example files

Three realistic deal documents are provided in `examples/` for testing:

| File                                | Deal type | Company                             | Key detail                                                |
| ----------------------------------- | --------- | ----------------------------------- | --------------------------------------------------------- |
| `buyout_teaser_acme_precision.txt`  | Buyout    | Acme Precision Components GmbH (DE) | €87.4M revenue, €19.3M EBITDA, 22% margin, 0.58x leverage |
| `growth_equity_teaser_synthai.txt`  | Growth    | SynthAI Analytics Ltd (UK)          | £14.2M ARR, 127% YoY growth, 138% NRR                     |
| `minority_stake_nordic_clinics.txt` | Minority  | Nordic Specialist Clinics AB (SE)   | SEK 892M revenue, 20% EBITDA margin, SEK 518M recurring   |

---

## API reference

### `GET /health`

Returns provider and model configuration.

```json
{ "status": "ok", "provider": "anthropic", "model": "claude-sonnet-4-6" }
```

### `POST /analyze`

**Content-Type:** `multipart/form-data`
**Field:** `files` (one or more files)
**Response:** `text/event-stream` — SSE stream as described above

```bash
curl -N -X POST http://localhost:8000/analyze \
  -F "files=@examples/buyout_teaser_acme_precision.txt"
```

---

## Limitations

- **Stateless by design.** No history, no database. Each request is independent.
- **Text extraction quality.** Image-only PDFs (fully scanned without OCR) may produce poor results even with the pymupdf fallback. Use OCR pre-processing for such documents.
- **LLM accuracy.** Metric extraction depends on document clarity and LLM capability. Values are returned as-found in the source — the agents do not calculate or interpolate missing figures.
- **No authentication.** The backend has no auth layer. Do not expose port 8000 publicly without adding authentication.
