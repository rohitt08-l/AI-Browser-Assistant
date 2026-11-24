# AI Browser Assistant (Chrome Extension + FastAPI + Multi-LLM)

## Overview

AI Browser Assistant is a Chrome side-panel extension that lets you chat with any webpage, much like "Ask Gemini" in Chrome.

It reads the article you're viewing (cleaned with Mozilla Readability) and lets you:

* Ask questions about the page, with follow-up questions in a real chat
* Highlight a passage and ask about just that part
* Summarize the page instantly
* Generate structured study notes
* Export a polished PDF document

Answers stream in token by token and render as Markdown. The backend works with **Groq**, **Azure OpenAI** or any **OpenAI-compatible** API, and can automatically fall back to a second provider if the first one fails.

---

## Features

* Side panel that stays open while you browse, with a separate conversation for each tab
* Streaming responses (Server-Sent Events) with a Stop button
* Clean content extraction: navigation, footers and ads are removed before anything reaches the model
* Smart context strategy: small pages are sent in full; long pages use BM25 or embedding retrieval for Q&A, and map-reduce over the whole page for summaries and notes
* Auto mode routes requests to Q&A / Summary / Notes / PDF using instant keyword rules, calling the LLM only when a request is ambiguous
* PDF export with safe Markdown rendering and a download link
* Provider fallback, retries and timeouts
* Startup config validation: a missing API key fails at boot, not on the first request
* Prompt-injection hardening: page text is wrapped as untrusted data
* No PyTorch, FAISS or LangChain, so the deploy image is small and cold starts are fast

---

## Architecture

```text
Extension (side panel)
  ├─ chrome.scripting → Readability extracts title / text / selection (on demand, no global content script)
  └─ POST /ask/stream ─────────────────────────────────────────────┐
                                                                   ▼
FastAPI backend                                                    
  ├─ Router: rules → (LLM only if ambiguous) → QA | SUMMARIZE | NOTES | GENERATE_DOC
  ├─ Context strategy
  │    ├─ page ≤ MAX_CONTEXT_TOKENS → send the whole page
  │    ├─ long page + QA            → retrieve top chunks (BM25 or embeddings API, cached)
  │    └─ long page + summary/notes → map-reduce over every section
  ├─ LLMService: Groq / Azure / OpenAI, pooled async clients, retries, fallback
  ├─ SSE stream: meta → status → token… → done(file_url)
  └─ PDF: Markdown → ReportLab → GET /files/{id} (auto-expires)
```

---

## Project Structure

```text
AI-Browser-Assistant/
├── backend/
│   ├── app.py                    # App factory, CORS, error handling, /health
│   ├── core/
│   │   ├── config.py             # pydantic-settings, validated at startup
│   │   └── errors.py
│   ├── models/schemas.py         # Request / response models
│   ├── routes/
│   │   ├── ask.py                # POST /ask (JSON) and POST /ask/stream (SSE)
│   │   └── files.py              # GET /files/{id}
│   └── services/
│       ├── assistant_service.py  # Orchestration + map-reduce
│       ├── context_service.py    # Chunking, BM25, retrieval, caching
│       ├── embeddings_service.py # Optional remote embeddings
│       ├── llm_service.py        # Providers, streaming, fallback
│       ├── router_service.py     # Task routing
│       ├── prompts.py            # Prompt templates
│       ├── pdf_service.py        # Markdown → PDF
│       └── file_store.py         # Temporary file storage with TTL
├── extension/
│   ├── manifest.json             # MV3, side panel, minimal permissions
│   ├── background.js
│   ├── sidepanel.html / .css / .js
│   ├── extractor.js              # Injected on demand
│   └── lib/                      # Vendored Readability, marked, DOMPurify
├── tests/                        # pytest suite (mocked LLM, no network)
├── .env.example
├── requirements.txt / requirements-dev.txt
└── Procfile
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/rohitt08-l/AI-Browser-Assistant.git
cd AI-Browser-Assistant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Then set at least `LLM_PROVIDER` and that provider's key:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `groq`, `azure` or `openai` |
| `LLM_FALLBACK_PROVIDER` | Optional second provider used if the primary one fails |
| `GROQ_API_KEY`, `GROQ_MODEL` | Groq |
| `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION` | Azure OpenAI |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | OpenAI or any OpenAI-compatible server |
| `EMBEDDINGS_PROVIDER` | `none` (BM25, default), `azure` or `openai`. Only used for Q&A on very long pages |
| `MAX_CONTEXT_TOKENS` | Pages up to this size are sent in full (default 10000; raise it on Azure or paid plans) |
| `CORS_ALLOW_ORIGIN_REGEX` | Lock to `^chrome-extension://<your-extension-id>$` in production |

### 3. Run the backend

```bash
uvicorn backend.app:app --reload
```

The API runs at `http://127.0.0.1:8000`, with interactive docs at `/docs`.

### 4. Load the extension

1. Open `chrome://extensions/` and enable **Developer mode**
2. Click **Load unpacked** and select the `extension/` folder
3. Click the toolbar icon (or press `Ctrl+Shift+Y`) to open the side panel
4. If your backend isn't at `http://localhost:8000`, set its URL from the ⚙️ settings in the panel

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/ask/stream` | SSE stream of `meta`, `status`, `token`, `done` and `error` events |
| `POST` | `/ask` | Same request, full JSON response `{answer, task, file_url}` |
| `GET` | `/files/{id}` | Download a generated PDF (expires after `FILE_TTL_SECONDS`) |
| `GET` | `/health` | Liveness and active provider |

Request body:

```json
{
  "question": "What are the main risks?",
  "task_type": "auto",
  "page_content": "...",
  "page_title": "...",
  "page_url": "https://...",
  "selection": "",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

`task_type` is one of `auto`, `qa`, `summarize`, `notes` or `generate_doc` (case-insensitive).

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use a fake LLM, so they need no API keys or network access.

---

## Roadmap

* **Phase 2 (security):** auth / BYOK, rate limiting and quotas, privacy policy
* **Phase 3 (quality and operations):** eval set, Sentry, LLM tracing, Docker + CI, Redis cache
* **AI features:** cited answers that jump to the passage, multi-tab chat, YouTube and PDF support, selection actions, agentic page actions

---

## Author

**Rohit Patil**, ML Engineer
