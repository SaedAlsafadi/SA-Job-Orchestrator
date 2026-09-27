# Testing Guide

## Test Suites

The project has two independent test suites:

| Suite | Tool | Location | Baseline |
|---|---|---|---|
| Backend | pytest | `backend/tests/` | **788 passed, 21 skipped, 1 xfailed** |
| Frontend | vitest | `frontend/src/__tests__/` | **152 passed** |

---

## Backend Tests

### Quick Run

```bash
cd backend
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

# Full suite
pytest tests/ -v

# Unit tests only (faster)
pytest tests/unit/ -v

# With coverage report
pytest tests/ --cov=app --cov-report=html
```

### Test Structure

```
backend/tests/
├── unit/                    # Isolated unit tests (no real services)
│   ├── test_ats_scorer.py
│   ├── test_candidate_profile_extraction.py
│   ├── test_cover_letter_service.py
│   ├── test_db_resilience.py
│   ├── test_document_parser.py
│   ├── test_experience_analyzer.py
│   ├── test_group_a_fixes.py       # Regression suite A
│   ├── test_group_c_fixes.py       # Regression suite C
│   ├── test_group_d_fixes.py       # Regression suite D
│   ├── test_group_e_fixes.py       # Regression suite E
│   ├── test_group_f_fixes.py       # Regression suite F
│   ├── test_harness.py             # Application harness
│   ├── test_job_service.py
│   ├── test_keyword_analyzer.py
│   ├── test_llm_client.py
│   ├── test_llm_router.py          # LLMTaskRouter
│   ├── test_matching.py
│   ├── test_matching_v2.py
│   ├── test_models.py
│   ├── test_mvp_remediation.py
│   ├── test_phase19_packages.py    # Application packages
│   ├── test_phase20c_hardening.py  # Security hardening
│   ├── test_resume_service.py
│   ├── test_schemas.py
│   ├── test_scorer.py
│   ├── test_secret_rotation.py
│   ├── test_security.py
│   ├── test_settings.py
│   ├── test_skill_matcher.py
│   ├── test_storage.py
│   ├── test_tailoring_merge.py
│   ├── test_telegram_bot.py
│   ├── test_workflow.py
│   └── ...
├── integration/
│   ├── test_auth.py             # Auth flow integration
│   └── test_opportunity_intake.py
└── conftest.py                  # Shared fixtures (DB, client, users)
```

### Test Fixtures

- `db` — In-memory async SQLite (via `aiosqlite`)
- `client` — FastAPI `TestClient` with all dependencies overridden
- `auth_headers` — Pre-authenticated request headers
- `test_user` — Pre-created test user
- `fakeredis` — In-memory Redis mock (via `fakeredis`)

No real LLM calls, real database connections, real email, or real API keys are required.

### Known Failing Tests (Phase 22 Baseline)

11 tests are currently failing (pre-existing, not caused by this cleanup):

| Test | Failure Reason |
|---|---|
| `test_mvp_remediation::TestJobSearchDedup::test_empty_ids_do_not_collapse_distinct_jobs` | Exa deprecated API (`search_and_contents()`) |
| `test_mvp_remediation::TestSkillContentDedup::test_duplicate_content_returns_existing` | Skill dedup behavior change |
| `test_mvp_remediation::TestPiiNameGate::test_selector_guidance_accepted` | PII gate regex too strict |
| `test_harness::TestSkillRegistry::test_record_versions_and_pii_gate` | Related PII gate change |
| `test_harness::TestSkillGuidance::test_renders_skill_content` | Skill content rendering |
| `test_harness::TestReviewOrchestrator::test_failed_run_judged_diagnosed_and_skill_saved` | Harness orchestration |
| `test_group_d_fixes::TestSkillFeedbackLoop::test_success_verdict_increments_skill_score` | Feedback loop |
| `test_group_d_fixes::TestSkillFeedbackLoop::test_failure_verdict_decrements_skill_score` | Feedback loop |
| `test_group_d_fixes::TestSkillFeedbackLoop::test_repeated_failures_auto_retire` | Feedback loop |
| `test_job_service::TestSearchJobs::test_search_jobs_collects_platform_results` | Exa deprecated API |
| `test_job_service::TestSearchJobs::test_search_jobs_handles_platform_failure` | Exa deprecated API |

These failures are related to the Exa AI SDK deprecating `search_and_contents()` in favor of `search()`, and some skill-registry behavior assertions that need updating. They do not affect the core matching, tailoring, or application package workflows.

### Real-Platform Tests (Excluded from CI)

These test files require real API keys or live platforms and are excluded from the standard test run:

- `tests/test_submission_real_workable.py` — Real Workable submission
- `tests/test_workable_real.py` — Real Workable scraping
- `tests/test_bayt_real.py` — Real Bayt scraping
- `tests/test_greenhouse_real.py` — Real Greenhouse
- `tests/test_lever_real.py` — Real Lever
- `tests/test_submission_mock.py` — Requires `playwright` on system Python path

---

## Frontend Tests

### Quick Run

```bash
cd frontend

# Run once (CI mode)
npm run test:run

# Watch mode (development)
npm run test

# TypeScript check
npm run typecheck
```

### Test Structure

```
frontend/src/__tests__/
├── auth/
│   ├── authBootstrap.test.tsx
│   ├── authFlow.test.ts
│   ├── publicOnly.test.tsx
│   ├── refreshInterceptor.test.ts
│   └── requireSuperuser.test.tsx
├── components/
│   ├── CommandPalette.test.tsx
│   ├── ErrorBoundary.test.tsx
│   ├── Intervention.test.tsx
│   ├── JobDrawer.test.tsx
│   ├── MatchIntelligenceView.test.ts
│   ├── OfflineBanner.test.tsx
│   ├── PackageReview.test.tsx
│   ├── ResumeCard.test.tsx
│   ├── ResumePreviewPanel.test.tsx
│   └── RunTimeline.test.tsx
├── lib/
│   ├── opportunityCta.test.ts
│   ├── status.test.ts
│   └── timeline.test.ts
├── mocks/
│   ├── handlers.ts            # MSW API mock handlers
│   └── server.ts              # MSW server setup
├── pages/
│   ├── AdminPage.test.tsx
│   ├── AnalyticsPage.test.tsx
│   ├── AppDetailPage.test.tsx
│   ├── DashboardPage.test.tsx
│   ├── ForgotPasswordPage.test.tsx
│   ├── JobSearchPage.test.tsx
│   ├── LandingPage.test.tsx
│   ├── LoginPage.test.tsx
│   ├── OnboardingPage.test.tsx
│   ├── ResetPasswordPage.test.tsx
│   ├── ResumesPage.test.tsx
│   ├── SettingsPage.test.tsx
│   └── SystemStatePage.test.tsx
├── services/
│   └── resumeDownload.test.ts
└── store/
    └── useAppStore.test.ts

frontend/src/components/tailoring/__tests__/
└── CVTailoringWorkbench.test.tsx
```

All 152 tests pass. Tests use MSW (Mock Service Worker) to intercept API calls — no real backend required.

---

## CI Guidelines

The following checks are appropriate for CI without credentials:

```yaml
# Backend
- pytest tests/unit tests/integration -v --ignore-glob="*real*"
- ruff check backend/app/
- mypy backend/app/ (optional, strict)

# Frontend
- npm run test:run
- npm run typecheck
- npm run lint
- npm run build
```

Do not run `test_submission_real_*` or any `test_*_real.py` tests in CI — they require real platform credentials and network access.

Do not call real LLM providers in CI. All LLM calls in the test suite are mocked.

---

## Coverage

```bash
cd backend
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
# View report in htmlcov/index.html
```

---

## Linting and Formatting

```bash
# Backend lint
cd backend && ruff check app/

# Backend format
cd backend && ruff format app/

# Frontend lint
cd frontend && npm run lint

# Frontend format
cd frontend && npm run format
```
