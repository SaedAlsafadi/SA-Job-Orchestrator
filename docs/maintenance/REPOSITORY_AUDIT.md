# Repository Audit — SA Job Orchestrator
**Generated:** 2026-09-27  
**Auditor:** Phase 22 Portfolio Release  
**Branch:** `portfolio-cleanup` (from `main` @ `88c86c4`)

---

## Stage 0 — Safety Checkpoint

| Item | Status |
|---|---|
| Current branch | `portfolio-cleanup` (created for this audit) |
| Latest commit | `88c86c4` — *fix: close beta readiness blockers* |
| Working tree status | **Untracked files only** — no uncommitted tracked changes |
| Tracked files with staged changes | None |
| Git remotes | `origin → https://github.com/SaedAlsafadi/SA-Job-Orchestrator.git` |
| Branches | `main` (remote + local), `portfolio-cleanup` (local) |

### Untracked Files (Working Tree)

All untracked files are in two categories:

1. **Root-level debug scripts** — not staged, never committed (see Stage 1)
2. **`backend/data/storage/users/testuser*/`** — runtime user upload/resume data — not tracked, **contains real personal documents**

The `.gitignore` already excludes `.env`, `*.db`, and `data/storage/` so no live secrets or databases are currently tracked.

---

## Stage 1 — Full Repository Inventory

### Classification Key
- **A** — Active production source code
- **B** — Active development tooling  
- **C** — Required configuration
- **D** — Required tests
- **E** — Current documentation
- **F** — Historical documentation
- **G** — Generated build artifacts
- **H** — Temporary debugging scripts
- **I** — Runtime data
- **J** — Cached files
- **K** — Sensitive files (not tracked — good)
- **L** — Obsolete or abandoned
- **M** — Unknown / review required

---

### Root Level Files

| File | Class | Tracked | Action | Notes |
|---|---|---|---|---|
| `README.md` | E | ✅ | **REWRITE** | Significantly outdated — "In Progress" items are now implemented |
| `ARCHITECTURE.md` | E | ✅ | **UPDATE** | Exists but partially outdated; move to `docs/` |
| `CLAUDE.md` | B | ✅ | **KEEP** | AI assistant conventions — useful for contributors |
| `.env.example` | C | ✅ | **KEEP** | Safe template with empty values |
| `.env.prod.example` | C | ✅ | **KEEP** | Production template |
| `.env` | K | ❌ | **KEEP UNTRACKED** | Contains real credentials — excluded by .gitignore |
| `.gitignore` | C | ✅ | **ENHANCE** | Needs additional exclusions |
| `.dockerignore` | C | ✅ | **KEEP** | |
| `alembic.ini` | C | ✅ | **KEEP** | Points to backend migrations |
| `Caddyfile` | C | ✅ | **KEEP** | Production reverse proxy config |
| `pyproject.toml` | B | ❌ | **REVIEW** | Root-level — unclear if active or legacy |
| `docker-compose.yml` | C | ✅ | **KEEP** | |
| `docker-compose.dev.yml` | C | ✅ | **KEEP** | |
| `docker-compose.prod.yml` | C | ✅ | **KEEP** | |
| `Dockerfile.api` | C | ✅ | **KEEP** | |
| `Dockerfile.backend` | C | ✅ | **KEEP** | |
| `Dockerfile.frontend` | C | ✅ | **KEEP** | |
| `Dockerfile.worker` | C | ✅ | **KEEP** | |
| `nginx.conf` | C | ✅ | **KEEP** | |
| `bootstrap.sh` | B | ✅ | **KEEP** | Setup script |
| `run-local.ps1` | B | ❌ | **KEEP** | Windows dev launcher — useful |
| `run-local.cmd` | B | ❌ | **KEEP** | Windows CMD launcher wrapper |
| `fix_indent.py` | H | ✅ | **DELETE** | Debugging patch script |
| `get_url.py` | H | ✅ | **DELETE** | Ad-hoc URL fetching script |
| `patch_env.py` | H | ✅ | **DELETE** | Env patching debug script |
| `patch_env_gemma.py` | H | ✅ | **DELETE** | Env patching debug script |
| `patch_env_liquid.py` | H | ✅ | **DELETE** | Env patching debug script |
| `patch_env2.py` | H | ✅ | **DELETE** | Env patching debug script |
| `patch_error.py` | H | ✅ | **DELETE** | Debug patch script |
| `patch_fetch.py` | H | ✅ | **DELETE** | Debug patch script |
| `patch_import_resume.py` | H | ✅ | **DELETE** | Debug patch script |
| `patch_profile_endpoints.py` | H | ✅ | **DELETE** | Debug patch script |
| `patch_tailor.py` | H | ✅ | **DELETE** | Debug patch script |
| `patch_upload.py` | H | ✅ | **DELETE** | Debug patch script |
| `rewrite_import.py` | H | ✅ | **DELETE** | Debug rewrite script |
| `rewrite_profile.py` | H | ✅ | **DELETE** | Debug rewrite script |
| `rewrite_workflow.py` | H | ✅ | **DELETE** | Debug rewrite script |
| `script.py` | H | ✅ | **DELETE** | Generic debug script |
| `script2.py` | H | ✅ | **DELETE** | Generic debug script |
| `update_api.py` | H | ✅ | **DELETE** | Debug API update script |
| `temp.html` | H | ✅ | **DELETE** | Temporary HTML file |
| `temp.tsx` | H | ✅ | **DELETE** | Temporary React file |
| `temp_app.tsx` | H | ✅ | **DELETE** | Temporary React file |
| `temp_profile.txt` | H | ✅ | **DELETE** | Temporary profile data |
| `test.py` | H | ✅ | **DELETE** | Ad-hoc test script |
| `test_candidate_cv.pdf` | I | ✅ | **DELETE** | ⚠️ Real candidate CV tracked in git |
| `test_get_url.py` | H | ✅ | **DELETE** | Ad-hoc URL test |
| `test_workable.py` | H | ✅ | **DELETE** | Ad-hoc Workable integration test |
| `test_workflow_run.py` | H | ✅ | **DELETE** | Ad-hoc workflow test |
| `workable_jobs.html` | H | ✅ | **DELETE** | Scraped HTML data |
| `fix_card.py` | H | ❌ | **GITIGNORE** | Not tracked — debug script |
| `fix_dashboard.py` | H | ❌ | **GITIGNORE** | Not tracked — debug script |
| `fix_resumecard.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `fix_resumecard2.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `fix_resumecard3.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `fix_resumes.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `fix_resumestest.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `fix_resumestest2.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `base_resume.txt` | I | ❌ | **GITIGNORE** | Not tracked — personal resume data |
| `check_changes.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `check_tailored.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `inspect_resumes.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `inspect_sqlite.py` | H | ❌ | **GITIGNORE** | Not tracked |
| `llm_smoke_test.py` | H | ✅ | **REVIEW** | May have integration test value |
| `smoke_test.py` | H | ✅ | **REVIEW** | May have integration test value |
| `walkthrough.md` | M | ✅ | **ARCHIVE** | Developer walkthrough — move to docs/history/ |
| `implementation_plan.md` | F | ✅ | **ARCHIVE** | Historical plan — move to docs/history/ |
| `test-baseline.md` | E | ✅ | **KEEP/UPDATE** | Valuable baseline record |
| `beta-readiness-configuration.md` | F | ✅ | **ARCHIVE** | Historical — move to docs/history/ |
| `BUG_LOG.md` | F | ✅ | **ARCHIVE** | Historical — move to docs/history/ |
| `e2e-validation-report.md` | F | ✅ | **ARCHIVE** | Historical E2E report |
| `first-live-submission.md` | F | ✅ | **ARCHIVE** | Historical milestone |
| `phase_17_report.md` | F | ✅ | **ARCHIVE** | Historical phase report |
| `phase_19_report.md` | F | ✅ | **ARCHIVE** | Historical phase report |
| `phase_20a3_report.md` | F | ✅ | **ARCHIVE** | Historical phase report |
| `html.txt` | H | ✅ | **DELETE** | Scraped HTML content |
| `urls.txt` | H | ✅ | **DELETE** | Ad-hoc URL collection |
| `state.json` | I | ✅ | **DELETE** | Runtime state dump |
| `settings.local.json` | K | ✅ | **GITIGNORE** | May contain local settings |
| `CACHEDIRX.TAG` | J | ✅ | **DELETE** | Python cache tag |

---

### Root-Level Directories (Unexpected)

| Directory | Class | Tracked | Action | Notes |
|---|---|---|---|---|
| `app/` | M | ❌ | **REVIEW** | May be a stale copy of backend/app |
| `autoapply-ai-job-search-interface/` | L | ❌ | **REVIEW** | Old interface clone/copy? |
| `build/` | G | ❌ | **GITIGNORE** | Build artifact |
| `cover_letter/` | G | ❌ | **GITIGNORE** | Generated cover letters? |
| `data/` | I | ❌ | **GITIGNORE** | Runtime data — includes user uploads |
| `dist/` | G | ❌ | **GITIGNORE** | Build artifact |
| `generated/` | G | ❌ | **GITIGNORE** | Generated files |
| `project/` | M | ❌ | **REVIEW** | Unknown |
| `resume/` | I | ❌ | **GITIGNORE** | Generated resumes? |
| `scripts/` | B | ❌ | **REVIEW** | May contain useful dev scripts |
| `sessions/` | I | ❌ | **GITIGNORE** | Browser sessions — sensitive |
| `src/` | M | ❌ | **REVIEW** | May be a stale frontend copy |
| `storage/` | I | ❌ | **GITIGNORE** | User file storage — private |
| `tests/` | D | ❌ | **REVIEW** | Root-level tests? |
| `tmp/` | H | ❌ | **GITIGNORE** | Temp files |
| `v/` | M | ❌ | **REVIEW** | Unknown |
| `node_modules/` | J | ❌ | **GITIGNORE** | Root node_modules? (frontend should own this) |
| `package.json` | M | ✅ | **REVIEW** | Root package.json — needed? |
| `index.html` | M | ✅ | **REVIEW** | Root index.html — needed? |
| `tsconfig.json` | M | ✅ | **REVIEW** | Root tsconfig — needed? |
| `vite.config.ts` | M | ✅ | **REVIEW** | Root vite config — needed? |
| `.pytest_cache/` | J | ❌ | **GITIGNORE** | |
| `.ruff_cache/` | J | ❌ | **GITIGNORE** | |
| `autoapply_backend.egg-info/` | G | ❌ | **GITIGNORE** | Build artifact |
| `.claude/` | M | ❌ | **GITIGNORE** | AI agent config — already gitignored |

---

### Backend (`backend/`)

| Path | Class | Action | Notes |
|---|---|---|---|
| `backend/app/` | A | **KEEP** | Core application code |
| `backend/app/api/` | A | **KEEP** | FastAPI routes |
| `backend/app/core/` | A | **KEEP** | Domain logic |
| `backend/app/core/llm/` | A | **KEEP** | LLMClient, LLMTaskRouter |
| `backend/app/core/ats/` | A | **KEEP** | ATS scoring engine |
| `backend/app/core/documents/` | A | **KEEP** | PDF/DOCX generation |
| `backend/app/core/automation/` | A | **KEEP** | Browser automation |
| `backend/app/core/job_discovery/` | A | **KEEP** | Discovery providers |
| `backend/app/core/harness/` | A | **KEEP** | Application harness |
| `backend/app/services/` | A | **KEEP** | Business logic |
| `backend/app/services/telegram/` | A | **KEEP** | Telegram integration |
| `backend/app/models/` | A | **KEEP** | SQLAlchemy models |
| `backend/app/schemas/` | A | **KEEP** | Pydantic schemas |
| `backend/app/db/` | A | **KEEP** | DB session + migrations |
| `backend/app/db/migrations/versions/` | A | **KEEP** | 23 Alembic migrations — never delete |
| `backend/app/workers/` | A | **KEEP** | Arq background workers |
| `backend/app/observability/` | A | **KEEP** | Structlog + Prometheus |
| `backend/tests/unit/` | D | **KEEP** | Unit test suite (791+ tests) |
| `backend/tests/integration/` | D | **KEEP** | Integration tests |
| `backend/pyproject.toml` | C | **KEEP** | Primary dependency file |
| `backend/app.db` | I | **GITIGNORE** | Runtime SQLite — already ignored |
| `backend/autoapply.db` | I | **GITIGNORE** | Runtime SQLite — already ignored |
| `backend/sa_jobs.db` | I | **GITIGNORE** | Runtime SQLite — already ignored |
| `backend/validate_cv.py` | H | ❌ | **GITIGNORE** | Debug script |
| `backend/walkthrough.md` | F | ✅ | **ARCHIVE** | Historical walkthrough |
| `backend/urls.txt` | H | ✅ | **DELETE** | Ad-hoc URL list |
| `backend/app/services/job_search.py.tmp` | H | ❌ | **GITIGNORE** | Temp file |
| `backend/data/storage/` | I | ❌ | **⚠️ PERSONAL DATA** | Contains real CV/resume uploads — see Stage 4 |
| `backend/tmp/` | H | ❌ | **GITIGNORE** | |

---

### Frontend (`frontend/`)

| Path | Class | Action | Notes |
|---|---|---|---|
| `frontend/src/` | A | **KEEP** | React SPA source |
| `frontend/src/__tests__/` | D | **KEEP** | 152-test suite |
| `frontend/src/components/` | A | **KEEP** | All components |
| `frontend/src/pages/` | A | **KEEP** | All pages |
| `frontend/src/hooks/` | A | **KEEP** | Custom React hooks |
| `frontend/src/services/` | A | **KEEP** | API clients |
| `frontend/src/store/` | A | **KEEP** | Zustand stores |
| `frontend/src/types/` | A | **KEEP** | TypeScript types |
| `frontend/src/lib/brand.ts` | A | ❌ | **STAGE AND COMMIT** | Untracked active source |
| `frontend/package.json` | C | ✅ | **KEEP** | |
| `frontend/package-lock.json` | C | ✅ | **KEEP** | |
| `frontend/vite.config.ts` | C | ✅ | **KEEP** | |
| `frontend/tsconfig.json` | C | ✅ | **KEEP** | |
| `frontend/measure.cjs` | H | ❌ | **GITIGNORE** | Performance measurement script |
| `frontend/measure.spec.ts` | H | ❌ | **GITIGNORE** | Performance spec — not unit test |
| `frontend/test-results/` | G | ❌ | **GITIGNORE** | Playwright test artifacts |
| `frontend/node_modules/` | J | ❌ | **GITIGNORE** | Already gitignored |

---

### Templates (`templates/`)

| Path | Class | Action | Notes |
|---|---|---|---|
| `templates/resume/*/template.html` | A | **KEEP** | 5 resume templates (classic, creative, executive, minimal, modern) |
| `templates/resume/*/style.css` | A | **KEEP** | |
| `templates/cover_letter/*/template.html` | A | **KEEP** | 3 cover letter templates |
| `templates/cover_letter/*/style.css` | A | **KEEP** | |

---

### Docs (`docs/`)

| File | Class | Action | Notes |
|---|---|---|---|
| `docs/beta-readiness-configuration.md` | F | **ARCHIVE → docs/history/** | Historical milestone |
| `docs/BUG_LOG.md` | F | **ARCHIVE → docs/history/** | Historical bug log |
| `docs/e2e-validation-report.md` | F | **ARCHIVE → docs/history/** | Historical E2E report |
| `docs/first-live-submission.md` | F | **ARCHIVE → docs/history/** | Historical milestone |
| `docs/phase_17_report.md` | F | **ARCHIVE → docs/history/** | |
| `docs/phase_19_report.md` | F | **ARCHIVE → docs/history/** | |
| `docs/phase_20a3_report.md` | F | **ARCHIVE → docs/history/** | |
| `docs/test-baseline.md` | E | **KEEP / UPDATE** | Baseline test results |

---

## Stage 2 — Deletion Safety Analysis

### Files Confirmed for Deletion (Tracked)

These files are tracked in git, have no production references, and contain no unique information:

| File | Reason | Reproducible? |
|---|---|---|
| `fix_indent.py` | One-off formatting fix applied and committed | Yes |
| `get_url.py` | Ad-hoc URL fetcher | Yes |
| `patch_env.py` | Applied env patch — committed | Yes |
| `patch_env_gemma.py` | Applied model patch — committed | Yes |
| `patch_env_liquid.py` | Applied model patch — committed | Yes |
| `patch_env2.py` | Applied env patch | Yes |
| `patch_error.py` | Applied error handling patch | Yes |
| `patch_fetch.py` | Applied fetch patch | Yes |
| `patch_import_resume.py` | Applied import patch | Yes |
| `patch_profile_endpoints.py` | Applied profile endpoint patch | Yes |
| `patch_tailor.py` | Applied tailoring patch | Yes |
| `patch_upload.py` | Applied upload patch | Yes |
| `rewrite_import.py` | Applied import rewrite | Yes |
| `rewrite_profile.py` | Applied profile rewrite | Yes |
| `rewrite_workflow.py` | Applied workflow rewrite | Yes |
| `script.py` | Generic debug script | Yes |
| `script2.py` | Generic debug script | Yes |
| `update_api.py` | Debug script | Yes |
| `temp.html` | Temp HTML from development | Yes |
| `temp.tsx` | Temp React fragment | Yes |
| `temp_app.tsx` | Old React page draft | Yes |
| `temp_profile.txt` | No personal data found (React code fragment) | Yes |
| `test.py` | Ad-hoc test | Yes |
| `test_candidate_cv.pdf` | ⚠️ Real PDF tracked in repo | N/A — remove entirely |
| `test_get_url.py` | Ad-hoc URL test | Yes |
| `test_workable.py` | Ad-hoc Workable test | Yes |
| `test_workflow_run.py` | Ad-hoc workflow test | Yes |
| `workable_jobs.html` | Scraped HTML | No unique value |
| `html.txt` | Scraped HTML text | No unique value |
| `urls.txt` | URL list | No unique value |
| `state.json` | Runtime state dump | No unique value |
| `CACHEDIRX.TAG` | Python cache tag | Auto-generated |
| `backend/urls.txt` | Backend URL list | No unique value |
| `llm_smoke_test.py` | LLM smoke test — no prod value | Yes |
| `smoke_test.py` | Smoke test — no prod value | Yes |

### Files Classified KEEP (No Deletion)

- All `backend/app/` source — never delete
- All `backend/tests/` — never delete
- All `backend/app/db/migrations/versions/` — never delete
- All `frontend/src/` source — never delete
- All `templates/` — never delete
- `CLAUDE.md`, `README.md`, `.gitignore`, `.env.example`, `pyproject.toml` (backend)
- All Docker configuration
- `run-local.ps1`, `run-local.cmd` — useful for local development

### Files Classified REVIEW_REQUIRED

| File | Concern |
|---|---|
| `root/package.json` | Root-level package — is it the old frontend root? |
| `root/index.html` | Root-level HTML — old frontend entry? |
| `root/tsconfig.json` | Root tsconfig — old frontend? |
| `root/vite.config.ts` | Root Vite config — old frontend? |
| `root/tsconfig.node.json` | Old frontend |
| `root/vite.e2e.config.ts` | Old e2e config |
| `root/measure.cjs` | Old perf script |
| `root/measure.spec.ts` | Old perf spec |
| `root/.eslintrc.cjs` | Old eslint |
| `root/.prettierrc` | Old prettier |
| `autoapply-ai-job-search-interface/` | Possible original fork copy |
| `app/` | Possible stale backend copy |
| `src/` | Possible stale frontend copy |

---

## Stage 3 — Secret and Privacy Audit

### Secrets in Working Tree (Not Tracked)

| File | Secret Type | Tracked | Status | Action |
|---|---|---|---|---|
| `.env` | Gemini API Key (`LLM__GEMINI_API_KEY`) | ❌ | Active | ⚠️ **ROTATE** — key exposed in untracked file |
| `.env` | Telegram Bot Token (`TELEGRAM_BOT_TOKEN`) | ❌ | Active | ⚠️ **ROTATE** — token in untracked file |
| `.env` | Auth Secret (`AUTH__SECRET_KEY=dev-insecure-change-me`) | ❌ | Insecure dev value | OK for dev, not for production |
| `.env` | Storage signing secret (`dev-insecure-change-me`) | ❌ | Insecure dev value | OK for dev |

> [!IMPORTANT]
> The `.env` file is excluded from git tracking by `.gitignore` — these credentials are NOT committed to history.
> However, **before making this repository public, you should rotate both credentials** because:
> 1. The Gemini API key may have accumulated usage history
> 2. The Telegram bot token is live and actively receiving messages

### Git History Scan Results

Scan performed across all commits for literal credential strings:
- ✅ Telegram bot token (value redacted from this document) — **NOT found in git history**
- ✅ Gemini API key (value redacted from this document) — **NOT found in git history**

Test fixtures in `backend/tests/unit/test_telegram_bot.py` use **fake tokens** (`123456:secret`, `123456:must-not-leak`) — these are clearly dummy values, not real credentials.

### `.env.example` — Verified Safe

All values in the tracked `.env.example` template are empty placeholders. No real credentials are present.

### Conclusion

- No credentials are leaked into git history
- The `.gitignore` is correctly excluding `.env`
- Action required: **rotate credentials before publishing repository** as a precaution

---

## Stage 4 — Personal Data Audit

### ⚠️ HIGH PRIORITY: Local User Uploads

The following directories contain **real personal documents** (CVs, resumes, uploaded files):

```
backend/data/storage/users/testuser0000000000000000000000aa/
  uploads/   — ~70+ PDF/DOCX files (candidate CV uploads from testing)
  resumes/   — ~22 DOCX files (generated tailored resumes)

data/storage/users/testuser0000000000000000000000aa/
  uploads/   — additional PDF/DOCX files
  resumes/   — additional DOCX files
```

**Status:** NOT TRACKED (excluded by `.gitignore` `data/storage/` rule) — these will NOT be published to GitHub.

**Action Required:** Leave as-is for local development. Confirm before making repo public that no `git add -A` or similar command accidentally stages these.

### Tracked Personal Data

| File | Content | Status | Action |
|---|---|---|---|
| `test_candidate_cv.pdf` | Real CV file (ReportLab-generated during testing) | ✅ **TRACKED** | **DELETE from git** |
| `temp_profile.txt` | Contains React component code, not personal data | ✅ Tracked | **DELETE** |
| `base_resume.txt` | Not tracked — may contain real resume text | ❌ Not tracked | **GITIGNORE** |

### Local SQLite Databases (Not Tracked)

```
backend/app.db
backend/autoapply.db  
backend/sa_jobs.db
```

These contain development/test data including candidate profiles, applications, and job data used during testing. They are excluded by `.gitignore` (`*.db` rule) and will NOT be published.

### Summary

- The `.gitignore` is successfully protecting personal data directories
- One tracked file (`test_candidate_cv.pdf`) should be removed
- No real personal data will be published if `.gitignore` is respected

---

## Stage 5 — .gitignore Recommendations

The current `.gitignore` is well-structured but needs enhancements:

### Missing Exclusions to Add

```gitignore
# Additional Python caches
.mypy_cache/
.ruff_cache/
autoapply_backend.egg-info/

# Root-level build artifacts (from old frontend position)
/dist/
/build/
/node_modules/
/src/

# Root-level debug and temp scripts
fix_*.py
patch_*.py
rewrite_*.py
check_*.py
inspect_*.py
smoke_test*.py
*_smoke_test.py
llm_smoke_test.py
get_base_resume.py
get_url*.py
update_api.py
script.py
script2.py
test_api*.py
test_live*.py
test_local.py
test_match_manual.py
test_merge.py
test_scrape*.py
test_grep.py
test_gemini.py
test_import.py
test_404.py
test_pw*.png
test_candidate_cv.pdf
validate_cv.py
e2e_script.py
create_cv.py
reset_alembic.py
base_resume.txt
temp_profile.txt
html.txt
urls.txt
state.json
workable_jobs.html
settings.local.json

# Frontend test artifacts
frontend/test-results/
frontend/measure.cjs
frontend/measure.spec.ts

# OS-specific
Thumbs.db
Desktop.ini
*.lnk

# Additional runtime dirs
/sessions/
/storage/
/cover_letter/
/resume/
/generated/
/v/
/tmp/
CACHEDIRX.TAG

# backend-specific
backend/tmp/
backend/app/services/job_search.py.tmp
backend/validate_cv.py
backend/data/storage/
```

---

## Stage 6 — Dependency Audit

### Backend Dependencies (`backend/pyproject.toml`)

| Package | Status | Notes |
|---|---|---|
| `fastapi>=0.111.0` | ✅ Active | Core framework |
| `uvicorn[standard]>=0.30.0` | ✅ Active | ASGI server |
| `pydantic>=2.7.0` | ✅ Active | Validation |
| `pydantic-settings>=2.3.0` | ✅ Active | Settings management |
| `sqlalchemy[asyncio]>=2.0.30` | ✅ Active | ORM |
| `aiosqlite>=0.20.0` | ✅ Active | Async SQLite |
| `alembic>=1.13.0` | ✅ Active | Migrations |
| `redis[hiredis]>=5.0.0` | ✅ Active | Queue/cache |
| `arq>=0.26.0` | ✅ Active | Background workers |
| `browser-use>=0.1.40` | ⚠️ Known issue | `BrowserConfig` API changed; tests skip |
| `playwright>=1.44.0` | ✅ Active | PDF rendering + browser automation |
| `playwright-stealth>=2.0.3` | ✅ Active | Anti-detection |
| `langchain-openai>=0.1.0` | ⚠️ Optional | Required by `browser-use` |
| `langchain-anthropic>=0.1.0` | ⚠️ Optional | Required by `browser-use` |
| `langchain-google-genai>=1.0.0` | ⚠️ Optional | Required by `browser-use` |
| `litellm>=1.40.0` | ✅ Active | LLM abstraction |
| `portkey-ai>=1.6.0` | ⚠️ Optional | Routing gateway |
| `weasyprint>=62.0` | ✅ Active | PDF generation |
| `python-docx>=1.1.0` | ✅ Active | DOCX handling |
| `jinja2>=3.1.0` | ✅ Active | Template rendering |
| `PyPDF2>=3.0.0` | ✅ Active | PDF parsing |
| `sentence-transformers>=2.7.0` | ✅ Active | Embedding |
| `faiss-cpu>=1.8.0` | ✅ Active | Vector search |
| `spacy>=3.7.0` | ✅ Active | NLP |
| `scikit-learn>=1.5.0` | ✅ Active | ML utilities |
| `python-telegram-bot>=22.0` | ✅ Active | Telegram integration |
| `exa-py>=1.1.0` | ✅ Active | Job discovery |
| `PyJWT>=2.8.0` | ✅ Active | Authentication |
| `pwdlib[argon2]>=0.2.0` | ✅ Active | Password hashing |
| `cryptography>=43.0.0` | ✅ Active | Secret encryption |
| `structlog>=24.1.0` | ✅ Active | Structured logging |
| `prometheus-client>=0.20.0` | ✅ Active | Metrics |
| `tenacity>=8.3.0` | ✅ Active | Retry logic |
| `httpx>=0.27.0` | ✅ Active | HTTP client |
| `alembic-postgresql-enum>=1.3.0` | ✅ Active | Migration helper |

**Known Limitation:** `beautifulsoup4` (`bs4`) is used by `bayt_provider.py` but is NOT declared in `pyproject.toml`. Tests importing this module fail with `ModuleNotFoundError: No module named 'bs4'`. The venv environment appears to have it installed, but it should be declared as an explicit dependency.

### Frontend Dependencies (`frontend/package.json`)

| Package | Status | Notes |
|---|---|---|
| `react@^18.2.0` | ✅ Active | UI framework |
| `react-dom@^18.2.0` | ✅ Active | |
| `react-router-dom@^6.21.0` | ✅ Active | Routing |
| `@tanstack/react-query@^5.0.0` | ✅ Active | Server state |
| `zustand@^4.4.0` | ✅ Active | Client state |
| `axios@^1.6.0` | ✅ Active | HTTP client |
| `i18next@^26.4.2` | ✅ Active | i18n |
| `react-i18next@^17.0.13` | ✅ Active | React i18n |
| `i18next-browser-languagedetector` | ✅ Active | Language detection |
| `vite@^5.0.0` | ✅ Active | Build tool |
| `vitest@^1.1.0` | ✅ Active | Test runner |
| `playwright@^1.63.0` | ⚠️ Dev-only | E2E tests — optional |
| `chromium@^3.0.3` | ⚠️ Review | May be redundant with playwright |

**Note:** The frontend has no Material UI dependency — the README's references to "React + MUI" appear to be outdated. The frontend uses a custom CSS/theme system.

---

## Summary of Actions Required Before Public Release

### Critical (Must Do)
1. **Rotate Gemini API key** — key was in `.env` during development
2. **Rotate Telegram bot token** — token was in `.env` during development
3. **Delete `test_candidate_cv.pdf`** from git history (it's tracked)
4. **Remove tracked debugging scripts** (see deletion list above)
5. **Verify `data/storage/` is gitignored** before any `git add`

### High Priority
6. **Update `.gitignore`** with additional exclusions
7. **Rewrite `README.md`** — current status section is significantly outdated
8. **Archive historical docs** to `docs/history/`
9. **Add `beautifulsoup4` to `pyproject.toml`** dependencies

### Medium Priority
10. **Create GitHub Actions CI workflow**
11. **Create `docs/ARCHITECTURE.md`** (current one at root is partially outdated)
12. **Create `docs/LOCAL_DEVELOPMENT.md`**
13. **Create `docs/TESTING.md`**
14. **Create `docs/SECURITY.md`**
15. **Create `docs/KNOWN_LIMITATIONS.md`**
16. **Verify license/attribution** — project was forked

### Low Priority
17. **Review root-level `package.json`, `vite.config.ts`** etc. — likely from old repo layout
18. **Add `frontend/src/lib/brand.ts`** to git (untracked active source file)
