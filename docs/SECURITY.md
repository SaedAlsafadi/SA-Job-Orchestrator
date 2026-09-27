# Security Reference

## Safety Defaults

The system is designed fail-closed. External actions are disabled by default.

| Feature | Default | Override |
|---|---|---|
| Live ATS submission | ❌ **Off** | `APPLY_MODE=autonomous` |
| Real email sending | ❌ **Off** | SMTP configuration + `MAILER__ENABLED=true` |
| Browser automation | ❌ **Off** | Playwright install + explicit trigger |
| Telegram bot | ❌ **Off** | `TELEGRAM_ENABLED=true` + valid token |
| Headful browser | ❌ **Off** | `BROWSER__HEADLESS=false` |
| External LLM calls | ❌ **Off** | Set at least one LLM provider key |

---

## Authentication

### JWT Tokens
- Access tokens: 15-minute expiry (`AUTH__ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh tokens: 30-day expiry (`AUTH__REFRESH_TOKEN_EXPIRE_DAYS`)
- Refresh token rotation: each use issues a new pair
- Token signing: HMAC-SHA256 with `AUTH__SECRET_KEY`

### Password Security
- Hashing algorithm: Argon2id (via `pwdlib[argon2]`)
- No plaintext passwords stored

### WebSocket Authentication
WebSocket connections authenticate with short-lived tickets (60-second expiry). The ticket is obtained via `GET /api/v1/ws/ticket` using a valid JWT. This prevents JWT token reuse in the WS handshake.

### Password Reset
Time-limited tokens stored hashed in the database. Tokens expire after use. Email delivery is required (disabled unless SMTP is configured).

---

## Tenant Isolation

All database operations are scoped to the authenticated user's `user_id`:

```python
# Example: every query includes the user_id constraint
stmt = select(Job).where(Job.user_id == current_user.id)
```

There is no cross-tenant data access, even for superusers querying data APIs (admin endpoints have separate, intentional scope).

---

## Credential Encryption

Per-user platform credentials (LinkedIn, Workable, etc.) are encrypted before storage using Fernet symmetric encryption:

```
User-provided credential
         │
         ▼
  Fernet.encrypt(credential, app_key)
         │
         ▼
  Stored in DB (ciphertext only)
```

The application-level key (`SECRETS__APP_KEYS`) is a comma-separated list of Fernet keys. The first key is the current encryption key; remaining keys are decryption-only (for key rotation).

Generate a key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Do not lose the encryption key** — encrypted credentials cannot be recovered.

---

## Approval Binding

Application package approval is cryptographically bound to the package contents:

1. Package assembled: tailored CV (PDF + DOCX) + cover letter + match report
2. SHA-256 hash computed over the package contents → stored as `ApplicationPackage.content_hash`
3. Approval created: `ApplicationApproval.package_hash = content_hash`
4. Before submission: current hash recomputed and compared to `ApplicationApproval.package_hash`
5. Mismatch → submission blocked (`ApplicationStatus.SUBMISSION_BLOCKED`)

This prevents stale approvals from being used after the application package is modified.

---

## Untrusted Job Descriptions

Job descriptions from external sources (scraped HTML, Telegram messages, Exa search results) are treated as untrusted data at all times:

- Job descriptions are stored as text blobs, not executed
- LLM prompts include instructions not to follow job-description instructions
- Job-description fields are never interpolated into system prompts
- Extracted structured data (title, company, requirements) is validated by Pydantic schema

---

## Data Privacy

### Local Storage
All user data (CVs, resumes, generated documents) is stored locally on the server filesystem. No data is sent to third-party services except:
- LLM providers (job descriptions, CV text, match results) — as required for AI processing
- Telegram API (job URLs, notification messages) — if Telegram is enabled

### What Is Sent to LLM Providers
- Job description text
- Candidate profile data (skills, experience, education)
- Generated CV/cover letter content (for QA review)

LLM calls include only the data needed for the specific task. No authentication tokens or credentials are included in LLM prompts.

### Data Retention
All data remains local to the running instance. No analytics or telemetry is sent externally. Prometheus metrics are exposed locally at `/metrics` (configurable).

---

## .env Security

Never commit `.env` files. The `.gitignore` excludes:
```
.env
.env.local
.env.*.local
.env.production
backend/.env
frontend/.env
```

The tracked `.env.example` contains only empty placeholders — no real values.

### Required Secret Rotation

If you have been running this system with credentials:

1. **Rotate your Gemini API key** — go to Google AI Studio and regenerate
2. **Rotate your Telegram bot token** — use `/revoke` with @BotFather
3. **Generate a new `AUTH__SECRET_KEY`** — all existing sessions will be invalidated
4. **Generate a new `STORAGE__URL_SIGNING_SECRET`**

---

## Production Checklist

Before any production deployment:

- [ ] `AUTH__SECRET_KEY` is a strong random value (32+ bytes)
- [ ] `STORAGE__URL_SIGNING_SECRET` is a strong random value
- [ ] `SECRETS__APP_KEYS` is set (generate with Fernet)
- [ ] All LLM API keys are production-grade and rate-limited
- [ ] `ENVIRONMENT=production`
- [ ] `APPLY_MODE=review` (or `autonomous` only after careful testing)
- [ ] HTTPS is configured (Caddy or nginx)
- [ ] Redis is password-protected
- [ ] Database is backed up
- [ ] Logs are not written to filesystem without rotation
- [ ] `DEBUG=false` / `LOG_LEVEL=WARNING` or `INFO`

---

## Responsible Use

This system automates parts of the job application process. Use responsibly:

- **Review all AI-generated content** before submission
- **Do not misrepresent qualifications** or fabricate experience
- **Respect platform terms of service** and rate limits
- **Protect stored credentials** — do not share `.env` files
- **Keep human approval in the loop** — `APPLY_MODE=review` is the safe default
- **Do not submit applications** on behalf of others without explicit consent
