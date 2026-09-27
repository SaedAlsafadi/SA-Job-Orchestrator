# SA Job Orchestrator

**An AI-assisted job application orchestration system** — full-stack, locally validated, with explainable match intelligence, human-in-the-loop review, and evidence-grounded CV tailoring.

> **Portfolio Project** — This repository represents completed engineering work, preserved as a technical reference. It is not a commercially deployed service.

---

## Project Status

| Area | Status |
|---|---|
| Core workflow (intake → match → tailor → package → approve) | ✅ **Implemented and locally validated** |
| Multi-tenant authentication and tenant isolation | ✅ Implemented |
| Redis/Arq async workflow queue | ✅ Implemented |
| Explainable match intelligence | ✅ Implemented |
| CV tailoring workbench with diff view | ✅ Implemented |
| Application packages with PDF/DOCX verification | ✅ Implemented |
| Approval binding to exact package version/hash | ✅ Implemented |
| Telegram opportunity intake | ✅ Implemented |
| Arabic/bilingual document generation | ✅ Implemented |
| LLM task routing (light/heavy model split) | ✅ Implemented |
| Backend test suite | ✅ **788 passing** |
| Frontend test suite | ✅ **152 passing** |
| External AI providers | ⚙️ Requires configuration |
| Browser automation (Workable, Greenhouse, Lever) | ⚙️ Implemented, requires Playwright |
| Live ATS submission | 🔴 **Disabled by default** |
| Real email sending | 🔴 **Off unless explicitly configured** |
| Production hosted platform | ❌ Not deployed |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite)                  │
│  Dashboard · Jobs · CV Tailoring · Applications · Profile   │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                  BACKEND (FastAPI)                          │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │  API Layer  │  │ Service Layer │  │ Background Workers │ │
│  │   /api/v1   │  │ (Business    │  │ (Arq + Redis)      │ │
│  │  + WebSocket│  │  Logic)       │  │                    │ │
│  └─────────────┘  └──────┬───────┘  └────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────▼─────────────────────────────┐  │
│  │               Core Modules                           │  │
│  │  LLMTaskRouter · ATS Scorer · Document Renderer     │  │
│  │  Match Intelligence · Tailoring · Harness           │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
     SQLite/Postgres         Redis              LLM Providers
     (SQLAlchemy async)    (Queue + Cache)    (Gemini/OpenAI/
     Alembic migrations                       Groq/OpenRouter)
```

---

## Key Engineering Features

### 1. LLM Task Router — Cost-Aware Model Routing
Separates LLM calls into **light tasks** (classification, metadata extraction, cleanup) and **heavy tasks** (match explanation, CV tailoring, QA, Arabic generation). Independently configurable per-environment, with a single bounded repair retry for structured output parse failures.

### 2. Explainable Match Intelligence
Multi-dimensional candidate-job analysis using: skills gap analysis, experience delta calculation, culture fit indicators, and GCC/KSA market eligibility. Returns structured, human-readable explanations with evidence grounding — not just a score.

### 3. Evidence-Grounded CV Tailoring
Tailoring suggestions must cite specific job-description evidence. The tailoring workbench presents a change-by-change diff view with accept/reject controls. No suggestion can be silently applied without human review.

### 4. Approval Binding
Application approval is cryptographically bound to the exact application package version/hash at time of approval. Any subsequent modification to a package automatically invalidates the prior approval — preventing stale-approval submission.

### 5. Multi-Tenant Architecture
Every database record carries a `user_id` foreign key. API middleware enforces tenant isolation — a user cannot read or modify another user's data even if they know the IDs. Row-level security enforced at query construction time.

### 6. Fail-Closed Safety
- Live ATS submission: **disabled by default** (`APPLY_MODE=review`)
- Real email delivery: requires explicit SMTP configuration
- Browser automation: requires Playwright install + explicit enablement
- Telegram: only activates when `TELEGRAM_ENABLED=true` AND a valid bot token is present

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript 5, Vite 5, Zustand, React Query, i18next |
| Backend | FastAPI, Python 3.11, async/await throughout |
| ORM | SQLAlchemy 2.0 (Mapped\[\] annotations), Alembic migrations |
| Queue | Redis + Arq (async job queue) |
| LLM | LiteLLM (unified provider interface), custom LLMTaskRouter |
| Documents | WeasyPrint (PDF), python-docx (DOCX), Jinja2 templates |
| Auth | PyJWT, Argon2 password hashing, Fernet credential encryption |
| Storage | Local filesystem (S3-compatible interface, pluggable) |
| Observability | Structlog (structured logging), Prometheus metrics |
| Browser | Playwright, playwright-stealth |
| Testing | pytest (788 tests), vitest (152 tests) |
| Containers | Docker Compose (dev + prod configurations) |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Redis (or Docker)

### Option 1: Windows One-Command Launcher

```powershell
cp .env.example .env
# Edit .env — set at least one LLM provider key
.\run-local.ps1
```

The launcher starts Redis, runs migrations, boots FastAPI, Arq worker, and Vite frontend. Logs to `.local-run/logs/`.

### Option 2: Docker Compose

```bash
cp .env.example .env
# Edit .env — set at least one LLM provider key
docker compose up --build
```

Development mode with hot reload:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Option 3: Manual Setup

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Arq worker (new terminal)
cd backend && python -m arq app.workers.tasks.WorkerSettings

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

### Service URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| OpenAPI Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| Prometheus Metrics | http://localhost:8000/metrics |

---

## Configuration

Copy `.env.example` to `.env`. Minimum required configuration:

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///data/db/autoapply.db
REDIS_URL=redis://localhost:6379/0

# LLM — set at least one provider
LLM__PREFERRED_PROVIDER=gemini
LLM__DEFAULT_MODEL=gemini/gemini-1.5-flash
LLM__GEMINI_API_KEY=your-key-here

# Application safety
APPLY_MODE=review          # autonomous | review | batch
ENVIRONMENT=development
```

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the complete configuration reference.

---

## Running Tests

```bash
# Backend
cd backend
python -m pytest tests/ -v

# Frontend
cd frontend
npm run test:run

# TypeScript check
cd frontend
npm run typecheck
```

**Baseline (Phase 22):**  
Backend: **788 passed, 21 skipped, 1 xfailed** | Frontend: **152 passed**

Tests do not require real LLM credentials, real email delivery, or live platform access. All external services are mocked.

---

## AI Architecture

```
User Action
    │
    ▼
LLMTaskRouter
    ├── Light Model (Gemini Flash / Groq Llama)
    │   ├── CLASSIFICATION
    │   ├── METADATA_EXTRACTION
    │   ├── TEXT_CLEANUP
    │   ├── SUMMARY
    │   └── MESSAGE_INTENT
    │
    └── Heavy Model (Gemini Pro / DeepSeek)
        ├── MATCH_DEEP + MATCH_EXPLANATION
        ├── CV_TAILOR + CV_REVIEW
        ├── APPLICATION_QA
        ├── ARABIC_GENERATION
        ├── COVER_LETTER
        └── APPLICATION_ANSWERS
```

Structured outputs use Pydantic schemas with JSON mode. Parse failures trigger one bounded repair attempt on the same model — provider failures, quota errors, and transport errors are never silently rerouted.

---

## Security and Responsible Use

- **No live submission by default.** `APPLY_MODE=review` means all applications require explicit human approval before any action.
- **No real email without SMTP.** Mailer is disabled unless explicitly configured.
- **No browser automation without Playwright.** Must be installed separately.
- **Approval is immutable.** Approval is hash-bound to the exact package version.
- **All AI-generated content requires human review.** No autonomous submission path exists for production use without deliberate configuration.
- **Tenant isolation.** All queries are scoped to the authenticated user's `user_id`.
- **BYO-key credential encryption.** Per-user platform credentials are encrypted with Fernet before storage.

Review AI-generated content before submission. Respect platform terms of service and automation policies. Do not misrepresent qualifications.

---

## Known Limitations

See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) for details.

Key limitations:
- `browser-use` package API has changed since integration; browser-automation tests are skipped
- `beautifulsoup4` is used by the Bayt discovery provider but not declared in `pyproject.toml`
- No production deployment exists; local-only validation
- Arabic document quality is provider-dependent
- Discovery orchestrator requires provider API keys (Exa AI) for job search
- 11 backend tests are failing in harness/dedup/job-service areas (see test baseline)

---

## Repository Layout

```
backend/app/
  api/              # FastAPI routes — /api/v1 + WebSocket
  core/
    ats/            # ATS scoring engine (multi-factor)
    automation/     # Browser automation (Playwright + stealth)
    documents/      # PDF/DOCX rendering (WeasyPrint + python-docx)
    harness/        # Application run harness (skill registry, review)
    job_discovery/  # Discovery providers (Exa, Bayt, LinkedIn, etc.)
    llm/            # LLMClient, LLMTaskRouter, prompts
    secrets/        # Fernet key encryption for credentials
  services/         # Business logic (matching, tailoring, workflow, etc.)
  models/           # SQLAlchemy models (23 Alembic migrations)
  schemas/          # Pydantic request/response schemas
  db/               # Async session, Redis, migration env
  workers/          # Arq background task handlers
  observability/    # Structlog + Prometheus

frontend/src/
  components/       # UI components (tailoring, matching, applications, etc.)
  pages/            # Route-level pages
  hooks/            # React hooks (data fetching, WebSocket, etc.)
  services/         # Axios API client layer
  store/            # Zustand state stores
  types/            # TypeScript type definitions

templates/
  resume/           # 5 HTML/CSS resume templates
  cover_letter/     # 3 HTML/CSS cover letter templates

docs/
  ARCHITECTURE.md
  CONFIGURATION.md
  LOCAL_DEVELOPMENT.md
  SECURITY.md
  TESTING.md
  KNOWN_LIMITATIONS.md
  demo/             # Demo walkthrough guide
  history/          # Historical engineering reports
  maintenance/      # Audit and portfolio release reports
```

---

## Attribution and License

This project was built on top of an open-source foundation. See [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) for the complete attribution statement including the upstream project, what was retained, and what was developed from scratch.

**Substantial custom development includes:**
- Full multi-tenant authentication system (JWT + Argon2)
- LLMTaskRouter with cost-aware light/heavy routing
- Explainable match intelligence engine
- CV tailoring workbench with evidence-grounded suggestions and diff review
- Application package system with hash-bound approval
- Arabic/bilingual document generation
- Telegram opportunity intake
- Harness-based application runner with skill registry
- 23 Alembic database migrations
- 788-test backend test suite
- 152-test frontend test suite

---

## Author

Saed Alsafadi — [github.com/SaedAlsafadi](https://github.com/SaedAlsafadi)

---

*This repository is made available for portfolio review and technical reference. It is not intended as a production product offering.*
