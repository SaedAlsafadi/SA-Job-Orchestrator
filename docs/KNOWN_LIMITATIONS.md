# Known Limitations

This document honestly describes the current limitations of SA Job Orchestrator as of September 2026.

---

## Browser Automation

### `browser-use` API Incompatibility

The `browser-use` package (v0.1.40+) changed its `BrowserConfig` API in a breaking way after integration. Tests that exercise browser-use-based automation are skipped with `pytest.mark.skip` or `xfail`.

**Affected:** Browser-based job submission, autonomous application completion  
**Workaround:** Playwright-direct automation (`submission_service.py`) is used for supported platforms (Workable, Greenhouse, Lever) and does not depend on `browser-use`  
**Status:** Known issue, not fixed in this release

---

## Undeclared Dependencies

### `beautifulsoup4` (bs4)

Used by `backend/app/core/job_discovery/providers/bayt_provider.py` for HTML parsing but not declared in `backend/pyproject.toml`.

**Impact:** `pip install -e ".[dev]"` will NOT install `bs4`. The Bayt discovery provider and its tests will fail with `ModuleNotFoundError: No module named 'bs4'`  
**Workaround:** `pip install beautifulsoup4` after installing the package  
**Status:** Should be added to `pyproject.toml` dependencies

---

## Test Suite

### 11 Failing Tests (Phase 22)

The following tests fail on the current `main` branch (pre-existing, not regressions from this cleanup):

**Exa API Deprecation (3 tests):**  
`exa-py` deprecated `search_and_contents()` in favor of `search()`. Tests that construct `SearchAndContents` requests fail.

**Skill Registry / Harness (6 tests):**  
Some skill registry, PII gate, and feedback loop tests have behavior assertions that diverge from the current implementation. These appear to be tests that were not updated when the implementation evolved.

**Job Search Dedup (2 tests):**  
A deduplication test (`test_empty_ids_do_not_collapse_distinct_jobs`) expects 3 results but gets 13 — likely the test was written against a DB fixture that no longer matches the actual test environment state.

**Impact:** These failures do not affect the core workflow (intake → match → tailor → package → approve). The 788 passing tests cover all primary functionality.

---

## Job Discovery

### Provider Limitations

| Provider | Status | Limitation |
|---|---|---|
| Exa AI | ✅ Working | Requires `EXA_API_KEY` |
| Bayt | ⚠️ Implemented | Requires `bs4` + live network |
| LinkedIn | ⚠️ Platform automation | Requires browser + login session |
| Indeed | ⚠️ Platform automation | Requires browser + login session |
| Glassdoor | ⚠️ Platform automation | Requires browser + login session |
| Workable | ✅ Direct API | Requires Workable API access |
| Greenhouse | ✅ Direct API | Job scraping via Greenhouse embed |
| Lever | ✅ Direct API | Job scraping via Lever API |

Platform automation providers (LinkedIn, Indeed, Glassdoor) require Playwright installed, a configured browser profile with an active login session, and explicit enablement. They are not tested in CI.

---

## AI/LLM

### Provider-Dependent Quality

AI-generated content quality (tailored CVs, cover letters, match explanations) varies significantly by:
- Which LLM provider is configured
- Which model is used (heavy vs. light)
- Job description quality

No accuracy claims are made. All generated content requires human review before use.

### Arabic Document Generation

Arabic text generation and right-to-left PDF rendering work but are limited by:
- Model's Arabic language capability (Gemini Pro recommended)
- WeasyPrint's RTL support (functional but not perfect)
- Font availability on the rendering server

### Structured Output Reliability

Structured JSON output (Pydantic schema-validated) has a single bounded repair retry. If both attempts fail to produce valid structured output, the workflow task fails. This is intentional (fail-closed) but can cause retries in production.

---

## No Production Deployment

This project has no hosted production environment. All validation was performed locally. The following production concerns are unverified:

- PostgreSQL performance under concurrent users
- Redis cluster failover
- S3 storage reliability
- Browser automation stability over long runs
- Memory usage of sentence-transformers under load
- LLM rate limiting and quota management at scale

---

## Frontend

### No MUI Dependency

The README previously described "React + MUI." The frontend does not use Material UI — it uses a custom CSS theme. Some documentation may still reference MUI.

### No Responsive Design Testing

The frontend was developed and tested at desktop viewport sizes. Mobile responsiveness has not been verified.

---

## Security

### Development Secrets

The default `AUTH__SECRET_KEY` and `STORAGE__URL_SIGNING_SECRET` values in `.env.example` are `dev-insecure-change-me`. These must be replaced before any production or public deployment.

### JWT Key Length Warning

Tests use a short JWT signing key that triggers a `InsecureKeyLengthWarning` from the `jwt` library. This is limited to test fixtures only.

---

## Documentation

### Outdated Root ARCHITECTURE.md

The `ARCHITECTURE.md` at the repository root was written during early development. The current authoritative architecture document is `docs/ARCHITECTURE.md`.

### Historical Phase Reports

Documents in `docs/history/` describe the system as it was during development (Phases 17–20). They may not reflect the final implementation. They are preserved as engineering history.
