# Architecture — SA Job Orchestrator

> **Last Updated:** September 2026  
> This document reflects the actual implemented architecture, verified against source code.

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Backend Architecture](#2-backend-architecture)
3. [Frontend Architecture](#3-frontend-architecture)
4. [AI Architecture](#4-ai-architecture)
5. [Data Architecture](#5-data-architecture)
6. [Infrastructure](#6-infrastructure)
7. [Application Workflow](#7-application-workflow)
8. [Security Architecture](#8-security-architecture)

---

## 1. System Overview

SA Job Orchestrator is a locally-operated job application system built around a human-in-the-loop philosophy. The system handles opportunity intake, explainable matching, evidence-grounded CV tailoring, and application package creation — with every externally-visible action gated by explicit human approval.

```
Opportunity Sources
  ├── Manual URL paste
  ├── Telegram bot intake
  └── Exa AI semantic search

        │
        ▼
    FastAPI Backend
        │
   ┌────┴────┐
   │  Async  │
   │  Queue  │ ← Redis / Arq
   │ Workers │
   └────┬────┘
        │
    LLMTaskRouter
        ├── Light Model → Classification, metadata, cleanup
        └── Heavy Model → Match, tailoring, QA, Arabic
        
        │
        ▼
    Application Package
    (PDF + DOCX + Match Report)
        │
        ▼
    Human Review / Approve
        │
        ▼
    Assisted Route Completion
    (Manual or Browser-assisted)
```

---

## 2. Backend Architecture

### Framework: FastAPI + Python 3.11

All backend code is async-first using `async def` + `await`. SQLAlchemy 2.0 is used with `AsyncSession` and `Mapped[]` type annotations.

### Module Structure

```
backend/app/
├── api/
│   └── v1/               # All REST routes (/api/v1/*)
│       ├── auth.py       # Registration, login, refresh, logout
│       ├── jobs.py       # Job search, list, detail, delete
│       ├── applications.py
│       ├── resumes.py    # Upload, list, generate, score, download
│       ├── analytics.py  # Dashboard, funnel, scores, LLM usage
│       ├── settings.py
│       ├── profile.py    # Candidate profile CRUD
│       ├── packages.py   # Application package management
│       ├── tailoring.py  # CV tailoring sessions
│       ├── opportunities.py  # Intake endpoint
│       └── ws.py         # WebSocket (ticket auth, event stream)
│
├── core/
│   ├── ats/              # ATS scoring engine
│   │   ├── scorer.py     # Multi-factor score calculation
│   │   ├── keyword_analyzer.py
│   │   └── experience_analyzer.py
│   ├── automation/       # Browser automation
│   │   ├── platforms/    # LinkedIn, Indeed, Glassdoor, Workable, Bayt, Greenhouse, Lever
│   │   └── session_manager.py
│   ├── documents/
│   │   ├── pdf_renderer.py   # WeasyPrint + Playwright PDF
│   │   ├── docx_renderer.py  # python-docx DOCX
│   │   └── parser.py         # PDF/DOCX text extraction
│   ├── harness/          # Application run harness
│   │   ├── skill_registry.py  # Platform connector skills
│   │   └── review_orchestrator.py
│   ├── job_discovery/    # Job search providers
│   │   └── providers/
│   │       ├── exa_provider.py
│   │       ├── bayt_provider.py
│   │       └── workable_provider.py
│   ├── llm/
│   │   ├── client.py     # LiteLLM wrapper with Prometheus metrics
│   │   ├── router.py     # LLMTaskRouter (light/heavy dispatch)
│   │   └── prompts/      # Typed prompt builders per task
│   ├── secrets/          # Fernet key encryption
│   └── storage/          # Storage backend (local/S3)
│
├── services/             # Business logic orchestration
│   ├── workflow_service.py    # Main pipeline orchestrator
│   ├── matching.py            # CandidateJobMatcher
│   ├── tailoring.py           # CV tailoring session management
│   ├── tailoring_merge.py     # Merge accepted changes into CV
│   ├── application_package.py # Package assembly + hashing
│   ├── pdf_verifier.py        # Package integrity verification
│   ├── resume.py              # Resume CRUD + text extraction
│   ├── cover_letter.py        # Cover letter generation
│   ├── question_engine.py     # Application Q&A resolution
│   ├── discovery_service.py   # Job discovery orchestration
│   ├── dispatch.py            # Submission dispatch
│   ├── submission_service.py  # Browser-based submission
│   ├── analytics.py
│   ├── account.py
│   ├── mailer.py
│   └── telegram/
│       ├── bot.py
│       ├── handlers.py
│       ├── intake.py
│       └── notifier.py
│
├── models/               # SQLAlchemy declarative models
│   ├── user.py
│   ├── job.py
│   ├── application.py
│   ├── resume.py
│   ├── candidate_profile.py  # Structured candidate data
│   ├── tailoring_session.py
│   ├── application_package.py
│   ├── application_approval.py  # Hash-bound approval records
│   ├── application_run.py
│   ├── application_route.py
│   ├── llm_usage.py           # Per-call LLM telemetry
│   └── enums.py               # Canonical StrEnum definitions
│
├── schemas/              # Pydantic v2 schemas (request/response)
├── db/
│   ├── session.py        # AsyncSession factory
│   ├── redis.py          # Redis connection
│   └── migrations/
│       ├── env.py        # Async migration runner
│       └── versions/     # 23 Alembic migrations (never delete)
│
├── workers/
│   └── tasks.py          # Arq task definitions + WorkerSettings
│
└── observability/        # Structlog + Prometheus
```

### Key Services

**WorkflowService** (`services/workflow_service.py`): Orchestrates the end-to-end pipeline from job analysis through application package assembly.

**CandidateJobMatcher** (`services/matching.py`): Invokes LLMTask.MATCH_DEEP and MATCH_EXPLANATION to produce structured, human-readable match intelligence.

**TailoringService** (`services/tailoring.py`): Manages tailoring sessions where the LLM proposes changes with evidence citations; users accept/reject individually.

**ApplicationPackageService** (`services/application_package.py`): Assembles the final package (tailored CV PDF/DOCX + cover letter + match report), computes a content hash, and binds it to the approval record.

**SubmissionService** (`services/submission_service.py`): Playwright-based form completion (disabled by default; requires explicit `APPLY_MODE=autonomous`).

---

## 3. Frontend Architecture

### Framework: React 18 + TypeScript + Vite

No component library dependency — custom CSS theme system with `frontend/src/styles/theme.css`.

### State Management
- **React Query** (`@tanstack/react-query`) — server state, caching, background refetch
- **Zustand** — client UI state (`useAppStore`, `useAuthStore`, `useProfileStore`, `useUiStore`)

### Key Pages

| Route | Component | Purpose |
|---|---|---|
| `/` | `LandingPage` | Public landing page |
| `/dashboard` | `DashboardPage` | Application overview + stats |
| `/jobs` | `JobSearchPage` | Job search + intake |
| `/applications` | `ApplicationsPage` | Application list |
| `/applications/:id` | `AppDetailPage` | Application timeline + detail |
| `/applications/:id/workflow` | `ApplicationWorkflow` | Review + approval workflow |
| `/resumes` | `ResumesPage` | Resume management |
| `/tailoring/:id` | `CVTailoringWorkbench` | Change-by-change review |
| `/profile` | `CandidateProfilePage` | Profile import + editing |
| `/settings` | `SettingsPage` | Provider config + preferences |
| `/analytics` | `AnalyticsPage` | Usage analytics |
| `/admin` | `AdminPage` | Superuser admin panel |

### Key Components

- `MatchIntelligenceView` — Renders match scores, skill gaps, and explanations
- `CVTailoringWorkbench` — Change card list with accept/reject, diff viewer
- `PackageReview` — Application package preview with approval gate
- `RunTimeline` — WebSocket-powered application run progress
- `ResumePreviewPanel` — PDF/DOCX preview before submission
- `TelegramSelector` — Telegram opportunity source selection

### WebSocket Integration

Real-time events flow from the backend Arq worker through Redis pub/sub to the frontend via `useWebSocket` hook. The WS connection uses ticket-based authentication (short-lived ticket, not the long-lived JWT).

---

## 4. AI Architecture

### LLMTaskRouter

The `LLMTaskRouter` (`core/llm/router.py`) splits all LLM calls into two categories:

```python
LIGHT_TASKS = {
    CLASSIFICATION, METADATA_EXTRACTION, TEXT_CLEANUP,
    SUMMARY, DEDUP_ASSISTANCE, SOURCE_CLASSIFICATION,
    DISCOVERY_PREPROCESS, MESSAGE_INTENT
}

HEAVY_TASKS = {
    MATCH_DEEP, JOB_REQUIREMENT_ANALYSIS, MATCH_EXPLANATION,
    CV_TAILOR, CV_REVIEW, APPLICATION_QA, ARABIC_GENERATION,
    ARABIC_REASONING, JOB_NORMALIZATION, ROUTE_RESOLUTION,
    COVER_LETTER, APPLICATION_EMAIL, APPLICATION_ANSWERS
}
```

Light model: configured via `LLM__LIGHT_MODEL` (default: `gemini/gemini-1.5-flash`)  
Heavy model: configured via `LLM__HEAVY_MODEL` (default: `gemini/gemini-1.5-pro`)

### Structured Outputs

All LLM calls that require structured data use `complete_with_structured_output()` with Pydantic schemas as the output type. A single bounded repair retry is attempted on parse failures. Provider failures and quota errors are never silently rerouted.

### LLM Client (`core/llm/client.py`)

Built on LiteLLM for unified provider access. Tracks per-call telemetry (tokens, cost estimate, model, purpose) to the `llm_usage` table. Exposed via Prometheus counter metrics.

### Evidence Grounding

CV tailoring suggestions carry a `job_evidence` field that must reference specific text from the job description. The frontend surfaces this evidence to the user during review. The LLM is instructed not to generate suggestions without evidence.

---

## 5. Data Architecture

### Database: SQLite (default) / PostgreSQL (optional)

Migrations managed by Alembic. The migration environment uses `async_engine_from_config` and `render_as_batch=True` for SQLite compatibility.

**23 migrations** spanning the project timeline:
- `0001` — Initial multi-tenant schema (users, jobs, applications, resumes)
- `0002` — Platform sessions
- `0003` — Application run harness tables
- `0004` — LLM purpose/general telemetry
- `0005` — Dedup and skills tracking
- `0006` — Password reset tokens
- `...0007–0023` — Candidate profiles, tailoring sessions, packages, approvals, routes, monitoring, Telegram, operational UX, LLM telemetry

### Key Models

```
User                    — Multi-tenant root
  └── Job               — Discovered/pasted opportunities
  └── Application       — Application lifecycle record
        └── ApplicationRun        — Individual run attempt
        └── ApplicationPackage    — Assembled package (hash)
        └── ApplicationApproval   — Hash-bound approval record
        └── ApplicationRoute      — Platform routing decision
  └── Resume            — Uploaded and generated resumes
  └── CandidateProfile  — Structured candidate data (JSON blobs)
        └── CandidateProfileVersion — Version history
  └── TailoringSession  — CV tailoring workflow state
  └── LLMUsage          — Per-call telemetry
  └── UserSettings      — Per-user preferences
  └── TelegramUser      — Telegram bot link
  └── PasswordResetToken
  └── SystemLock        — Distributed locking
```

### Storage

File storage uses a pluggable backend (`STORAGE__PROVIDER=local|s3`). Local storage is organized as:
```
data/storage/
  users/{user_id}/
    uploads/    — Original CV uploads (PDF/DOCX)
    resumes/    — Generated tailored resumes
```

---

## 6. Infrastructure

### Docker Compose

Three configurations:
- `docker-compose.yml` — Production services (backend, worker, frontend, Redis)
- `docker-compose.dev.yml` — Development overrides (hot reload, volume mounts)
- `docker-compose.prod.yml` — Production overrides (Caddy reverse proxy)

### Reverse Proxy

Caddy (`Caddyfile`) handles HTTPS, routing, and compression for production.

### Background Queue

Arq (async Redis-backed job queue). Workers defined in `backend/app/workers/tasks.py`. The worker imports `WorkerSettings` which declares available functions and Redis configuration.

---

## 7. Application Workflow

```
1. INTAKE
   └── User pastes URL / Telegram bot receives link / Exa AI search

2. JOB PROCESSING
   └── LLM extracts: title, company, requirements, skills, location, type
   └── Job saved to DB with provenance metadata

3. MATCH ANALYSIS
   └── CandidateJobMatcher runs MATCH_DEEP + MATCH_EXPLANATION
   └── Produces: score, skill gaps, experience delta, culture indicators
   └── Result stored, surfaced in MatchIntelligenceView

4. CV TAILORING
   └── LLM proposes changes with job-description evidence citations
   └── User reviews change-by-change in CVTailoringWorkbench
   └── Accepted changes merged into base profile via TailoringMerge
   └── TailoredResumeData assembled

5. PACKAGE ASSEMBLY
   └── Tailored CV rendered to PDF + DOCX (WeasyPrint / python-docx)
   └── Cover letter generated
   └── PDF/DOCX integrity verified
   └── Package content hash computed → stored in ApplicationPackage

6. HUMAN REVIEW + APPROVAL
   └── User reviews complete package in PackageReview
   └── Approval creates ApplicationApproval record (bound to package hash)
   └── Any modification to package after approval invalidates it

7. ROUTE + COMPLETION
   └── ApplicationRoute record determines submission method:
       MANUAL / EMAIL / BROWSER_AUTOMATION / PLATFORM_NATIVE
   └── Browser automation: Playwright + stealth fills form
   └── Screenshots captured to storage
   └── Status updated via WebSocket events
```

---

## 8. Security Architecture

### Authentication
- JWT access tokens (15-minute expiry) + refresh tokens (30-day expiry)
- Argon2id password hashing via `pwdlib`
- Refresh token rotation on each use
- Password reset via time-limited tokens (email delivery optional)

### Tenant Isolation
Every API endpoint resolves `current_user` from the JWT and passes `user_id` to all service calls. SQLAlchemy queries always include `WHERE user_id = :user_id`. There is no admin bypass that allows accessing other users' data.

### Credential Encryption
Per-user platform credentials (LinkedIn, Workable, etc.) are encrypted with Fernet before storage. The application-level encryption key (`SECRETS__APP_KEYS`) must be provided at startup. If absent, a dev-mode ephemeral key is generated (not suitable for production).

### WebSocket Auth
WebSocket connections use a short-lived ticket (60-second expiry) issued by a REST endpoint. The ticket is checked on WS connect. This prevents JWT reuse in the WS handshake.

### Approval Integrity
`ApplicationApproval.package_hash` stores a SHA-256 hash of the full package contents. Before any submission attempt, the system recomputes the hash and compares it to the stored value. Mismatch → submission blocked.

### Safety Defaults
- `APPLY_MODE=review` — all applications require explicit user approval
- `TELEGRAM_ENABLED=false` — Telegram bot disabled unless explicitly enabled
- `BROWSER__HEADLESS=true` — browser automation runs headless
- `ENVIRONMENT=development` — conservative settings by default
