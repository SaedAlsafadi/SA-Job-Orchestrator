# Configuration Reference

## Environment File

Copy `.env.example` to `.env` in the repository root. The application reads this file on startup.

```bash
cp .env.example .env
```

---

## Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///data/db/autoapply.db` | Database connection string |

SQLite is the default (no additional setup). For PostgreSQL:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/autoapply
```
Install `asyncpg`: `pip install -e ".[postgres]"`

---

## Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |

Redis is required for the Arq background worker queue and WebSocket pub/sub.

---

## LLM Providers

Set at least one provider API key. The system attempts the preferred provider first, then falls back in order.

| Variable | Description |
|---|---|
| `LLM__PREFERRED_PROVIDER` | Primary provider: `gemini`, `openai`, `groq`, `openrouter` |
| `LLM__FALLBACK_PROVIDERS` | JSON array: `["groq", "openrouter", "gemini"]` |
| `LLM__DEFAULT_MODEL` | LiteLLM model string, e.g. `gemini/gemini-1.5-flash` |
| `LLM__LIGHT_MODEL` | Model for light tasks (classification, metadata) |
| `LLM__HEAVY_MODEL` | Model for heavy tasks (tailoring, matching, QA) |
| `LLM__TEMPERATURE` | Default temperature (0.7) |
| `LLM__MAX_TOKENS` | Default max tokens (4096) |
| `LLM__GEMINI_API_KEY` | Google Gemini API key |
| `LLM__OPENAI_API_KEY` | OpenAI API key |
| `LLM__GROQ_API_KEY` | Groq API key |
| `LLM__OPENROUTER_API_KEY` | OpenRouter API key |
| `LLM__GITHUB_TOKEN` | GitHub Marketplace token (optional) |
| `LLM__PORTKEY_API_KEY` | Portkey gateway key (optional) |

### Recommended Configuration (Gemini)

```env
LLM__PREFERRED_PROVIDER=gemini
LLM__GEMINI_API_KEY=your-key-here
LLM__DEFAULT_MODEL=gemini/gemini-1.5-flash
LLM__LIGHT_MODEL=gemini/gemini-1.5-flash
LLM__HEAVY_MODEL=gemini/gemini-1.5-pro
```

### Cost-Effective Configuration (Groq)

```env
LLM__PREFERRED_PROVIDER=groq
LLM__GROQ_API_KEY=your-key-here
LLM__DEFAULT_MODEL=groq/llama-3.1-8b-instant
LLM__LIGHT_MODEL=groq/llama-3.1-8b-instant
LLM__HEAVY_MODEL=groq/llama-3.3-70b-versatile
```

---

## Authentication and Security

| Variable | Default | Description |
|---|---|---|
| `AUTH__SECRET_KEY` | `dev-insecure-change-me` | JWT signing secret — **must be changed in production** |
| `AUTH__ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token lifetime |
| `AUTH__REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime |
| `AUTH__WS_TICKET_EXPIRE_SECONDS` | `60` | WebSocket ticket lifetime |

Generate a strong secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Credential Encryption

| Variable | Default | Description |
|---|---|---|
| `SECRETS__PROVIDER` | `local` | Secrets backend: `local` only |
| `SECRETS__APP_KEYS` | (empty) | Comma-separated Fernet keys for credential encryption |

Generate a Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If `SECRETS__APP_KEYS` is empty in development, an ephemeral key is generated on startup (credentials are lost on restart). Always set this in production.

For key rotation, prepend the new key (first key = current, remaining = decryption-only):
```env
SECRETS__APP_KEYS=new-key,old-key
```

---

## File Storage

| Variable | Default | Description |
|---|---|---|
| `STORAGE__PROVIDER` | `local` | Storage backend: `local` or `s3` |
| `STORAGE__LOCAL_ROOT` | `./data/storage` | Local storage root directory |
| `STORAGE__URL_SIGNING_SECRET` | `dev-insecure-change-me` | Signed URL secret — change in production |

### S3-Compatible Storage (Cloudflare R2 / AWS S3 / MinIO)

```env
STORAGE__PROVIDER=s3
STORAGE__BUCKET=autoapply
STORAGE__REGION=auto
STORAGE__ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
STORAGE__ACCESS_KEY_ID=your-key-id
STORAGE__SECRET_ACCESS_KEY=your-secret-key
```

Install S3 support: `pip install -e ".[aws]"`

---

## Server

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Allowed CORS origins |
| `ENVIRONMENT` | `development` | Environment: `development` or `production` |
| `LOG_LEVEL` | `INFO` | Log level |

---

## Application Behavior

| Variable | Default | Description |
|---|---|---|
| `APPLY_MODE` | `review` | Application mode (see below) |
| `MIN_ATS_SCORE` | `0.75` | Minimum ATS score to proceed |

### Apply Modes

| Mode | Behavior |
|---|---|
| `review` | Applications require explicit human approval before any submission |
| `autonomous` | Applications are enqueued for automated submission after preparation (⚠️ use carefully) |
| `batch` | Multiple applications queued; user reviews and approves the batch |

**`review` is the default and recommended mode.**

---

## Browser Automation

| Variable | Default | Description |
|---|---|---|
| `BROWSER__HEADLESS` | `true` | Run browser headless |
| `BROWSER__MAX_PARALLEL` | `3` | Maximum parallel browser sessions |
| `BROWSER__USER_DATA_DIR` | `./data/sessions/chrome_profile` | Chrome profile directory |
| `BROWSER__KEEP_ALIVE` | `true` | Keep browser alive between uses |
| `BROWSER__MAX_STEPS` | `50` | Maximum automation steps per run |
| `BROWSER__MAX_FAILURES` | `3` | Maximum failures before abort |
| `BROWSER__STEP_TIMEOUT` | `120` | Step timeout in seconds |
| `BROWSER__USE_VISION` | `auto` | Vision mode: `auto`, `true`, `false` |

---

## Telegram

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_ENABLED` | `false` | Enable Telegram bot |
| `TELEGRAM_POLLING` | `true` | Use polling (vs webhook) |
| `TELEGRAM_BOT_TOKEN` | (empty) | Bot token from @BotFather |
| `TELEGRAM_BOT_USERNAME` | (empty) | Bot username |

---

## Job Discovery

| Variable | Default | Description |
|---|---|---|
| `EXA_API_KEY` | (empty) | Exa AI search API key (optional) |

---

## Platform Credentials (Optional)

These are only needed if browser automation will perform first-time logins. If `BROWSER__USER_DATA_DIR` points to a Chrome profile where you're already logged in, these can be left empty.

```env
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=
INDEED_EMAIL=
INDEED_PASSWORD=
GLASSDOOR_EMAIL=
GLASSDOOR_PASSWORD=
```

These credentials are encrypted before storage if provided via the settings API.
