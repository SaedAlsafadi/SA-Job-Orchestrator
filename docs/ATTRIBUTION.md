# Attribution

## Project Foundation

SA Job Orchestrator was built on top of an open-source foundation. The original project provided the initial repository structure, some base configuration patterns, and the starting point for the frontend scaffolding.

> **Note:** The original upstream project information has not been fully verified. If you are reviewing this for license compliance, please check the git history for the initial commit and any `LICENSE` file from that commit.

---

## License

This project's license follows from the original fork's license. The current `LICENSE` file at the repository root should be consulted for the applicable terms.

If no `LICENSE` file is present or its terms are unclear, **this repository should not be treated as openly licensed** without explicit clarification from the author.

---

## What Was Retained from the Original Project

The following may have been retained from or inspired by the upstream project:
- Initial project directory structure concept
- Base Docker Compose configuration patterns
- Some frontend component scaffold

Exact attribution cannot be determined without examining the initial commit against the upstream repository.

---

## What Was Developed from Scratch

The following represents substantial original development by Saed Alsafadi:

### Backend

**Authentication and Security**
- Full multi-tenant JWT authentication system
- Argon2id password hashing
- Refresh token rotation
- WebSocket ticket authentication
- Password reset flow

**Core AI/LLM Architecture**
- `LLMTaskRouter` — light/heavy task routing with cost-aware model selection
- `LLMClient` — LiteLLM wrapper with Prometheus telemetry
- All prompt templates (`backend/app/core/llm/prompts/`)
- Structured output with bounded repair retry
- Evidence-grounded tailoring schema

**Match Intelligence**
- `CandidateJobMatcher` — multi-dimensional match scoring
- ATS scoring engine (multi-factor: skills, keywords, experience, education)
- Match explanation generation with skill gap analysis
- GCC/KSA market eligibility assessment

**CV Tailoring System**
- `TailoringService` — session-based change management
- `TailoringMerge` — applying accepted changes to base profile
- Diff view data preparation

**Application Package System**
- `ApplicationPackageService` — package assembly + hashing
- `ApplicationApproval` model + hash-bound approval logic
- `PDFVerifier` — post-render integrity check
- `SubmissionService` — Playwright-based form completion

**Candidate Profile**
- `CandidateProfile` model with versioned JSON blobs
- CV import pipeline (PDF/DOCX → structured profile via LLM)
- Profile editing workflow

**Discovery and Intake**
- `DiscoveryOrchestrator` — multi-provider job search
- Exa AI semantic search integration
- Bayt/Workable/Greenhouse/Lever provider adapters
- Telegram opportunity intake (`TelegramIntake`, `TelegramBot`)

**Infrastructure**
- Redis/Arq async worker architecture
- WebSocket event bus (Redis pub/sub → frontend)
- Prometheus metrics instrumentation
- Structlog structured logging
- Fernet credential encryption
- S3-compatible storage backend

**Database**
- 23 Alembic migrations (complete history)
- All SQLAlchemy models with async support
- Canonical `enums.py` with `StrEnum` definitions

**Testing**
- 788-test backend test suite
- Shared fixtures (in-memory DB, fakeredis, mock LLM)
- All unit tests for the above systems

### Frontend

**CV Tailoring Workbench**
- `CVTailoringWorkbench` page — change-by-change review UI
- `ChangeCard`, `DiffViewer`, `ResumePreview` components

**Match Intelligence View**
- `MatchIntelligenceView` — structured match report display

**Application Workflow**
- `ApplicationWorkflow` page
- `PackageReview` — package preview with approval gate
- `RunTimeline` — WebSocket-powered run progress
- `InterventionModal` — human intervention interface

**Opportunity Intake**
- `TelegramSelector` — Telegram source selection
- Opportunity intake forms

**Authentication UI**
- Complete auth flow (login, register, forgot password, reset, refresh interceptor)

**Profile Management**
- `CandidateProfilePage` — profile import and editing

**i18n**
- Arabic/English internationalization (`i18n.ts`)

**Testing**
- 152-test frontend test suite (vitest + MSW)

---

## Third-Party Libraries

All third-party libraries are listed in `backend/pyproject.toml` and `frontend/package.json`. Key dependencies and their licenses:

| Library | License | Use |
|---|---|---|
| FastAPI | MIT | Web framework |
| SQLAlchemy | MIT | ORM |
| Alembic | MIT | Database migrations |
| LiteLLM | MIT | LLM abstraction |
| Pydantic | MIT | Data validation |
| WeasyPrint | BSD | PDF generation |
| python-docx | MIT | DOCX generation |
| Playwright | Apache 2.0 | Browser automation |
| sentence-transformers | Apache 2.0 | Embeddings |
| React | MIT | Frontend framework |
| Vite | MIT | Build tool |
| Zustand | MIT | State management |
| React Query | MIT | Server state |
| python-telegram-bot | LGPL-3.0 | Telegram integration |
| structlog | MIT | Logging |
| Prometheus client | Apache 2.0 | Metrics |
| PyJWT | MIT | JWT handling |
| cryptography | Apache 2.0 / BSD | Fernet encryption |

No commercial or proprietary libraries are used.

---

## Original Author

Saed Alsafadi  
GitHub: [github.com/SaedAlsafadi](https://github.com/SaedAlsafadi)
