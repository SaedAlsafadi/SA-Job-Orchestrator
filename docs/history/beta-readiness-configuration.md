# Beta deployment configuration

This is the production-readiness inventory for the beta. It is not a deployment guide and does not enable live submission.

## Required services and secrets

| Category | Required configuration | Beta requirement |
| --- | --- | --- |
| Database | `DATABASE_URL` | Use a durable PostgreSQL database. Run `alembic upgrade head` before starting the API. |
| Queue | `REDIS_URL` | Redis must be reachable by both the API and the Arq worker. |
| Worker | `REDIS_URL` plus the same application environment as the API | Run `arq app.workers.tasks.WorkerSettings`; monitor the worker health check and queue depth. |
| Authentication | `AUTH__SECRET_KEY`, access/refresh lifetimes, `AUTH__WS_TICKET_EXPIRE_SECONDS` | Generate a strong unique signing secret. Never use the development default in production. |
| Secret storage | `SECRETS__PROVIDER`, `SECRETS__APP_KEYS` | Configure a durable Fernet key set; the first key is the active encryption key. Do not rely on the development ephemeral key. |
| AI provider | At least one supported `LLM__*_API_KEY`, `LLM__PREFERRED_PROVIDER`, `LLM__LIGHT_MODEL`, `LLM__HEAVY_MODEL` | Current routing uses OpenRouter. Provider failure must remain explicit; do not add an unapproved fallback model. |
| Telegram | `TELEGRAM_ENABLED`, `TELEGRAM_POLLING`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` | Enable only after both token and public username are configured. The username must match Telegram `getMe`. The token is backend-only. Polling is the supported update mode. |
| Document storage | `STORAGE__PROVIDER` and provider-specific `STORAGE__*` values | Use durable S3-compatible storage for a multi-instance deployment, or a persistent local volume for a single instance. Set a strong `STORAGE__URL_SIGNING_SECRET`. |
| Transactional email | `EMAIL__PROVIDER` and `EMAIL__FROM_*`; SMTP settings only when intentionally enabled | Keep `EMAIL__PROVIDER=log` for a beta with real sending disabled. Configure `smtp` and credentials only after an explicit sending decision. |
| Browser/front-end origins | `CORS_ORIGINS`, `FRONTEND_URL`, `EMAIL__FRONTEND_BASE_URL`, frontend `VITE_API_BASE_URL`/`VITE_WS_URL` when not using the same-origin proxy | List exact HTTPS origins. Never use wildcard credentialed CORS. |
| Monitoring | `METRICS_TOKEN`, optional `SENTRY_DSN`, log destination/retention | Protect production metrics with a bearer token. Unknown model cost remains `UNKNOWN`, never zero. Alert on API/worker failures and queue backlog. |

The reverse proxy/TLS hostname is supplied as `DOMAIN` by `docker-compose.prod.yml`. API and worker containers must receive the same application configuration, except for process-specific command settings.

## Beta-safe feature flags

Keep these values unless a later, separately approved phase changes them:

```dotenv
BROWSER__LIVE_APPLY=false
ENABLE_LIVE_SUBMISSION=false
BROWSER__HEADLESS=true
EMAIL__PROVIDER=log
TELEGRAM_ENABLED=false
```

- `BROWSER__LIVE_APPLY=false` prevents the worker from driving a real application flow.
- `ENABLE_LIVE_SUBMISSION=false` blocks the legacy submission service's final submit operation.
- `BROWSER__HEADLESS=true` avoids unapproved headful browser automation.
- `EMAIL__PROVIDER=log` prevents real transactional delivery.
- Change `TELEGRAM_ENABLED` to `true` only after the token and username are configured and verified.

Application package generation remains available with these defaults. EMAIL-route content generation is not the same as sending an email; external delivery remains disabled until a real provider is deliberately configured.

## Pre-start checks

1. Confirm the migration head and run migrations against the target database.
2. Verify PostgreSQL and Redis health from the API and worker networks.
3. Confirm API and worker use the same auth, secret-storage, AI, Telegram, and document-storage configuration.
4. Confirm the production frontend and WebSocket URLs use HTTPS/WSS and exact allowed origins.
5. Verify live submission and real email delivery are still disabled.
6. If Telegram is enabled, verify `getMe` matches `TELEGRAM_BOT_USERNAME` before exposing the connection flow.
7. Exercise health, metrics authentication, error reporting, and worker queue telemetry before accepting traffic.
