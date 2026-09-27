# Local Development Guide

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Required (3.13 works) |
| Node.js | 18+ | For frontend |
| Redis | 7+ | Or Docker |
| Git | Any | |

---

## Option 1: Windows One-Command Launcher (Recommended)

The `run-local.ps1` script manages the entire local stack:

```powershell
# 1. Clone and enter the repository
git clone https://github.com/SaedAlsafadi/SA-Job-Orchestrator.git
cd SA-Job-Orchestrator

# 2. Set up environment
cp .env.example .env
# Edit .env — set at least one LLM provider key

# 3. Launch everything
.\run-local.ps1
```

The launcher:
- Checks for required dependencies (`-CheckOnly` to inspect only)
- Installs Python and frontend dependencies if missing (use `-SkipInstall` to prevent)
- Starts Redis (or detects existing instance / Docker)
- Runs Alembic migrations
- Starts FastAPI, Arq worker, and Vite frontend
- Writes logs to `.local-run/logs/`
- Waits for API and frontend readiness before returning
- Stops only the processes it started on `Ctrl+C`

```powershell
# Check prerequisites only (no start)
.\run-local.ps1 -CheckOnly

# Start without auto-installing dependencies
.\run-local.ps1 -SkipInstall

# Install Playwright Chromium for browser automation development
.\run-local.ps1 -InstallBrowser

# Use Docker Compose instead of native processes
.\run-local.ps1 -Mode Docker

# CMD wrapper (double-click friendly)
.\run-local.cmd
```

---

## Option 2: Docker Compose

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env — set at least one LLM provider key

# 2. Start all services (backend, worker, frontend, Redis)
docker compose up --build

# Development mode with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Services start on:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Option 3: Manual Setup (Step by Step)

### Step 1: Clone

```bash
git clone https://github.com/SaedAlsafadi/SA-Job-Orchestrator.git
cd SA-Job-Orchestrator
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` — minimum required:

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///data/db/autoapply.db
REDIS_URL=redis://localhost:6379/0

# LLM — set at least one of these:
LLM__GEMINI_API_KEY=your-gemini-api-key
LLM__GROQ_API_KEY=your-groq-api-key
LLM__OPENROUTER_API_KEY=your-openrouter-key

# These are safe dev defaults — change in production:
AUTH__SECRET_KEY=dev-insecure-change-me
STORAGE__URL_SIGNING_SECRET=dev-insecure-change-me
APPLY_MODE=review
ENVIRONMENT=development
```

### Step 3: Start Redis

```bash
# If Redis is installed natively:
redis-server

# If using Docker:
docker run -d -p 6379:6379 redis:7-alpine
```

### Step 4: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Create data directories
mkdir -p data/db data/storage data/sessions data/logs

# Run database migrations
alembic upgrade head

# Start FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Arq Worker (separate terminal)

```bash
cd backend
.venv\Scripts\activate  # if not already active
python -m arq app.workers.tasks.WorkerSettings
```

### Step 6: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

Frontend starts on http://localhost:3000 (or 5173 if 3000 is busy).

---

## Service URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| OpenAPI / Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |
| Prometheus Metrics | http://localhost:8000/metrics |
| Redis | localhost:6379 |

---

## Creating a Test Account

Once the backend is running, register via the API or the frontend:

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"StrongP@ssw0rd"}'

# Then login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"StrongP@ssw0rd"}'
```

Or use the registration page at http://localhost:3000.

---

## Optional: AI Configuration

The system requires at least one LLM provider to process jobs:

| Provider | Environment Variable | Notes |
|---|---|---|
| Google Gemini | `LLM__GEMINI_API_KEY` | Recommended — Flash (light) + Pro (heavy) |
| Groq | `LLM__GROQ_API_KEY` | Fast, free tier available |
| OpenRouter | `LLM__OPENROUTER_API_KEY` | Access to many models |
| OpenAI | `LLM__OPENAI_API_KEY` | GPT-4o |

Configure light and heavy models separately:
```env
LLM__PREFERRED_PROVIDER=gemini
LLM__DEFAULT_MODEL=gemini/gemini-1.5-flash
LLM__LIGHT_MODEL=gemini/gemini-1.5-flash
LLM__HEAVY_MODEL=gemini/gemini-1.5-pro
```

---

## Optional: Telegram Integration

```env
TELEGRAM_ENABLED=true
TELEGRAM_POLLING=true
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_BOT_USERNAME=your-bot-username
```

The Telegram bot allows submitting job URLs via chat message. Requires a bot created via @BotFather.

---

## Optional: Browser Automation

Browser automation is disabled by default. To enable:

1. Install Playwright browsers:
```bash
cd backend
.venv\Scripts\activate
playwright install chromium
```

2. For stealth anti-detection:
```bash
pip install playwright-stealth
```

3. Configure:
```env
BROWSER__HEADLESS=true
BROWSER__USER_DATA_DIR=./data/sessions/chrome_profile
```

> **Note:** Browser automation requires explicit `APPLY_MODE=autonomous` or manual trigger. It is never activated automatically in `review` mode.

---

## Resetting the Database

```bash
cd backend
.venv\Scripts\activate

# Delete and recreate
Remove-Item data/db/autoapply.db -ErrorAction SilentlyContinue
alembic upgrade head
```

---

## Common Issues

### Redis Connection Refused
Ensure Redis is running before starting the backend. The health endpoint (`GET /health`) shows Redis status.

### `ModuleNotFoundError: No module named 'playwright'`
Install Playwright: `pip install playwright && playwright install chromium`

### `ModuleNotFoundError: No module named 'bs4'`
Install beautifulsoup4: `pip install beautifulsoup4`  
(This is a known undeclared dependency in `pyproject.toml` — see KNOWN_LIMITATIONS.md)

### Migrations fail
Ensure `DATABASE_URL` in `.env` points to a writable directory. For SQLite the directory must exist.

### Frontend fails to connect to backend
Check `CORS_ORIGINS` in `.env` includes your frontend URL:
```env
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```
