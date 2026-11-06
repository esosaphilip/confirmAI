# confirmAI — Invoice ↔ Order-Confirmation Matcher

> An AI-assisted procurement tool that verifies a supplier's **invoice** against the
> original **order confirmation (Auftragsbestätigung, "AB")** and flags price
> deviations outside a configurable tolerance — with a full audit trail.

**Stack:** Python · FastAPI · LangChain · Ollama (Mistral + Nomic embeddings) · ChromaDB · React 18 · TypeScript · Vite

---

## The problem

In B2B procurement, a buyer agrees a price in an **order confirmation** and later
receives an **invoice** from the same supplier. Invoices frequently drift from the
agreed price — a unit price changes, a total creeps up, or a discount is dropped.
Catching these deviations today is a manual, error-prone, line-by-line PDF reading
exercise that doesn't scale.

**confirmAI automates the check:** upload the two PDFs, and it extracts the relevant
totals, compares them against your tolerance rule, and returns a **POSITIVE / NEGATIVE**
verdict with the supporting evidence.

---

## Why it's interesting (design decisions)

This project deliberately **does not hand the decision to an LLM.** Instead it separates
fuzzy extraction from hard decisions:

| Concern | Owner | Why |
|---|---|---|
| Reading numbers out of messy PDFs | **LLM** (Mistral via Ollama) | Documents vary in layout, language and formatting; an LLM handles that variance. |
| Deciding pass/fail | **Deterministic Python** | Financial decisions must be reproducible and auditable — no hallucinated thresholds. |

This "**AI extracts, code decides**" split is the core architectural idea:

- The LLM is only ever asked for a **single number** (the document net total), never a judgement.
- Retrieval is scoped with **separate vector stores per document type** so the model never
  confuses the AB total with the invoice total.
- The model output is parsed defensively (`_parse_amount`) to tolerate German `1.234,56`
  and English `1,234.56` number formats and stray punctuation.
- The final comparison is a one-line, provable arithmetic check — visible in the
  **tolerance log** the UI shows the user.

Every run produces a timestamped log, so a result can be reconstructed after the fact.

---

## How it works

```
                    ┌──────────────────────────────────────────────┐
   AB.pdf  ─────────▶│  1. Index the AB      PyPDFLoader → split →   │
   Invoice.pdf ─────▶│                       Chroma (own store)      │
                    └──────────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────────────┐
                    │  2. Extract the net total                    │
                    │     similarity search (totals-focused query) │
                    │     → Mistral → parse to float               │
                    └──────────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────────────┐
                    │  3. Evaluate (deterministic, no AI)          │
                    │     |invoice − ab| > tolerance ? NEGATIVE    │
                    │                      : POSITIVE              │
                    └──────────────────────────────────────────────┘
```

Three visible pipeline steps — **Indexing the AB → Indexing the invoice → Running the
tolerance evaluator** — are surfaced to the UI in real time so the user sees progress
instead of a spinner.

---

## Architecture

```
┌────────────────────────┐        HTTP / JSON         ┌─────────────────────────┐
│  React + Vite + TS     │  ────────────────────────▶ │  FastAPI (api.py)       │
│  (frontend/)           │   POST /verifications      │  • upload handling      │
│                        │   GET  /verifications/:id  │  • background jobs      │
│  • Verify screen       │   GET/PUT /rules           │  • job state + polling  │
│  • Rules editor        │  ◀──────────────────────── │  • CORS                 │
│  • Running view        │      job snapshot          └───────────┬─────────────┘
│  • Result screen       │                                        │
└────────────────────────┘                                        ▼
                                                     ┌─────────────────────────┐
                                                     │  RAG pipeline           │
                                                     │  indexing.py            │
                                                     │  vergleicher.py         │
                                                     │  • LangChain            │
                                                     │  • Ollama mistral       │
                                                     │  • nomic-embed-text     │
                                                     │  • ChromaDB (per doc)   │
                                                     └─────────────────────────┘
```

**Backend** ([api.py](api.py)) — a browser-friendly upload API. Because a browser can't
send a server-side file path, the API was refactored to accept **multipart PDF uploads**,
run the pipeline as a **background task**, and expose a **pollable job snapshot**. CORS
is enabled for the Vite dev server. Uploads are capped at 20 MB and validated as PDFs;
each run gets an isolated working directory that is cleaned up on completion.

**Pipeline** ([indexing.py](indexing.py), [vergleicher.py](vergleicher.py)) — PyPDFLoader →
recursive character splitting → Chroma vector store (one store per document) → similarity
search scoped to *totals* → Mistral extracts the net total → deterministic tolerance check.

**Frontend** ([frontend/](frontend)) — React 18 + React Router + TypeScript (strict mode),
built with Vite. Implements the four screens of the product design: **Verify**, **Rules**,
**Running**, and **Result**.

---

## Screens

The UI follows a supplied product design (`confirmAI.pdf`, included in the repo).

| Screen | Purpose |
|---|---|
| **New verification** | Drag & drop the AB and invoice PDFs, see validation badges, set tolerance, run. |
| **Matching rules** | Edit `price_tolerance_eur` with quick presets (Exact / €1 / €5 / €25) and a live impact preview. |
| **Running** | Live step-by-step progress (`STEP 2 OF 3`) with the active tolerance shown. |
| **Result** | POSITIVE/NEGATIVE banner, financial summary, discrepancies, and a dark monospace tolerance log. |

> History and per-line-item breakdown are stubbed for a later phase.

---

## Getting started

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **[Ollama](https://ollama.com)** running locally with the required models:

```bash
ollama pull mistral:latest
ollama pull nomic-embed-text:latest
```

### 1. Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" python-multipart \
            langchain-ollama langchain-community langchain-text-splitters \
            chromadb pypdf

uvicorn api:app --reload --port 8000
```

The API is now at `http://127.0.0.1:8000` (interactive docs at `/docs`).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to the backend, so no
environment configuration is needed.

---

## API reference

Base path: `/api/v1`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + active model/embedding names. |
| `GET` | `/rules` | Read the current rule config. |
| `PUT` | `/rules` | Update `price_tolerance_eur`. |
| `POST` | `/verifications` | Upload `ab_file` + `invoice_file` (+ optional `price_tolerance_eur`). Returns **202** with a job snapshot. |
| `GET` | `/verifications/{run_id}` | Poll job state: `steps`, `log`, and `result` when complete. |

<details>
<summary>Example: run a verification with curl</summary>

```bash
# 1. Start a run
RUN_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/verifications \
  -F "ab_file=@AB_4500123456.pdf" \
  -F "invoice_file=@RE-2026-10871.pdf" \
  -F "price_tolerance_eur=5" | python3 -c "import sys,json;print(json.load(sys.stdin)['run_id'])")

# 2. Poll the result
curl -s http://127.0.0.1:8000/api/v1/verifications/$RUN_ID | python3 -m json.tool
```

</details>

---

## Example run

With an AB net total of **€12,350.00**, an invoice net total of **€12,480.00**, and a
tolerance of **€5.00**:

```json
{
  "state": "completed",
  "result": {
    "status": "NEGATIVE",
    "ab_price": 12350.0,
    "invoice_price": 12480.0,
    "difference": 130.0,
    "tolerance": 5.0,
    "ab_number": "AB 4500123456",
    "invoice_number": "RE-2026-10871"
  },
  "log": [
    { "type": "config",  "message": "price_tolerance_eur = 5.00" },
    { "type": "index",   "message": "AB indexed from AB_4500123456.pdf" },
    { "type": "index",   "message": "invoice indexed from RE-2026-10871.pdf" },
    { "type": "extract", "message": "ab.total_net = 12350.00" },
    { "type": "extract", "message": "invoice.total_net = 12480.00" },
    { "type": "compare", "message": "abs_diff = 130.00" },
    { "type": "result",  "message": "130.00 > 5.00 -> NEGATIVE" }
  ]
}
```

The invoice is €130.00 above the AB, exceeding the €5.00 tolerance → **NEGATIVE**.

---

## Project structure

```
confirmAI/
├── api.py              # FastAPI app: upload endpoints, background jobs, job state
├── indexing.py         # PDF → chunks → Chroma vector store
├── vergleicher.py      # Extraction (LLM) + deterministic tolerance comparison
├── confirmAI.pdf       # UI/product design reference
├── frontend/           # React + Vite + TypeScript app
│   └── src/
│       ├── pages/      # Verify, Rules, Running, History screens
│       ├── components/ # AppShell, FileDrop, StepList, ResultView
│       ├── api.ts      # Typed API client
│       ├── types.ts    # Shared types mirroring the backend schemas
│       └── styles.css  # Design system (tokens extracted from the design)
└── data/runs/          # Per-run working dirs (git-ignored, cleaned up automatically)
```

---

## Limitations & roadmap

This is a working prototype, and it's honest about its edges:

- **Single-process, in-memory state.** Job state lives in a dict; restarting the server
  drops history. Production would use Redis/Postgres and a real task queue.
- **Totals only.** The comparison currently focuses on document net totals. Per-line-item
  discrepancy detection (the "2 found" detail in the result screen) is the next milestone.
- **History screen** is a placeholder.
- **Local models.** Extraction relies on a locally running Ollama; there is no hosted
  fallback, so accuracy tracks the chosen model.

### Roadmap

- [ ] Per-line-item price comparison with the discrepancy table
- [ ] Persistent run history and report export
- [ ] Pluggable extractor interface (Ollama / OpenAI / Anthropic)
- [ ] Docker Compose for a one-command local environment
- [ ] Evaluation harness: labelled document pairs + extraction accuracy metrics

---

## License

Not yet licensed. Add one before redistributing.
