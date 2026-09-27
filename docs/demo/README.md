# Demo Guide

> **Portfolio Project** — This guide describes how to present SA Job Orchestrator as an engineering portfolio demonstration.

---

## Recommended Demo Format

**Option B (Recommended): Recorded Walkthrough**

A recorded local walkthrough is the recommended demo format because:
- No sensitive live data is exposed
- No real job applications are triggered
- The full workflow can be shown in controlled sequence
- Screen recording can be edited for clarity

A public interactive frontend demo would require significant additional work to create safe fictional fixtures and a hardened demo mode.

---

## Pre-Demo Setup

### 1. Ensure Local Stack is Running

```powershell
.\run-local.ps1
```

Wait for both the API and frontend to report ready.

### 2. Verify Health

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy",...}
```

### 3. Create a Demo User

Use the registration page at http://localhost:3000 or the API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"DemoPassword123!"}'
```

### 4. Load Demo Profile

Use the profile import feature to load a fictional candidate profile.

**Fictional Candidate:**
```
Name: Alex Jordan
Email: alex.jordan@example.com  (fictional)
Current Role: Senior Software Engineer
Experience: 7 years
Skills: Python, FastAPI, React, PostgreSQL, Redis, Docker, Kubernetes
```

**Important:** Use entirely fictional data. Do not use real personal information in recordings that may be shared publicly.

---

## Suggested 90-Second Walkthrough Script

### Screen 1: Dashboard (10 seconds)
**Show:** Application overview with statistics
- Total applications, pipeline stages
- Recent activity

*Narrate: "The dashboard shows the current application pipeline state..."*

### Screen 2: Job Intake (15 seconds)
**Show:** Paste a job URL or description into the intake form
- Use a public job listing (e.g., from a company careers page)
- Show the URL being processed

*Narrate: "Job opportunities can come from multiple sources — direct URL, Telegram, or Exa semantic search..."*

### Screen 3: Match Intelligence (20 seconds)
**Show:** The explainable match intelligence view
- Match score breakdown
- Skill gap visualization
- Match explanation text with evidence

*Narrate: "The match engine explains why a candidate fits or doesn't fit, citing specific job requirements..."*

### Screen 4: CV Tailoring Workbench (20 seconds)
**Show:** The tailoring workbench with proposed changes
- A few change cards with evidence citations
- Accept/reject controls
- Diff view of before/after

*Narrate: "Each tailoring suggestion is grounded in the job description. The user reviews and accepts changes individually — nothing is applied automatically..."*

### Screen 5: Application Package Review (15 seconds)
**Show:** The assembled application package
- PDF/DOCX preview
- Package contents (CV + cover letter + match report)
- Approval button

*Narrate: "The approval binds to the exact package content. Any subsequent change to the package invalidates the approval..."*

### Screen 6: Application Timeline (10 seconds)
**Show:** The application run timeline
- Status progression
- WebSocket-powered real-time updates

---

## Screenshot Checklist

For a portfolio README or slide deck, capture these screens:

| Screen | Key Elements to Show |
|---|---|
| Dashboard | Application stats, pipeline view |
| Job Intake | URL input, platform selector |
| Match Intelligence | Score breakdown, skill gap, explanation text |
| CV Tailoring Workbench | Change cards, evidence citations, accept/reject |
| Diff Viewer | Before/after CV comparison |
| Application Package | PDF preview, approval gate |
| Application Timeline | Status progression |
| Settings | LLM provider configuration |
| Candidate Profile | Structured profile sections |

### Screenshot Requirements

All screenshots must:
- Use fictional or clearly sanitized data
- Not expose real email addresses or phone numbers
- Not show real API keys (blur or pixelate settings screenshots)
- Not reveal local file paths with personal information

---

## Demo Data Guidelines

### What to Use

```
Fictional Candidate:
  Name: Alex Jordan / Sam Chen / Jordan Riley
  Email: alex@example.com
  Phone: +1 (555) 000-0000
  Address: 123 Main Street, San Francisco, CA

Fictional Employer:
  Company: Acme Corp / Initech / Globex
  Role: Senior Software Engineer
  Location: Remote / San Francisco, CA
```

### What NOT to Use

- Your real name, email, or phone number
- Real candidate CVs from testing (these are in `backend/data/storage/` — not tracked)
- Real company names with real job listings (use generic descriptions)
- Real API keys (visible in screenshots)

---

## Interactive Demo Mode (Future)

If a public interactive demo is developed in the future, it must:

1. Use only fictional candidate and employer data
2. Prohibit real external actions:
   - `APPLY_MODE=review` hard-coded
   - SMTP disabled
   - LLM calls mocked or rate-limited
   - Telegram disabled
   - Browser automation disabled
3. Run in an isolated environment (separate DB, Redis)
4. Make the demo nature obvious to visitors
5. Expire demo sessions after a fixed time
6. Not expose any production secrets

This work is estimated at 2–3 days of engineering effort and is not included in the current portfolio release.
