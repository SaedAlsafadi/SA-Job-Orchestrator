# Phase 19: Application Intelligence and Email Application Workflow — Implementation Report

## 1. Pre-implementation architecture audit

A full inspection pass was performed before any code was written (per the phase mandate).
Findings, verified against the actual code rather than docs:

**Already existed:** `Application`/`ApplicationRun`/`ApplicationApproval` (single-use, expiring)
models; the `ApplicationStatus` state machine (`WAITING_FOR_REVIEW`, `SUBMITTING`,
`SUBMISSION_UNKNOWN`, `APPLIED`, `FAILED`, `SUBMISSION_BLOCKED`); the `LLMTask` enum already
declaring `COVER_LETTER`, `APPLICATION_EMAIL`, `APPLICATION_ANSWERS`, `APPLICATION_QA` routed to
the heavy model (DeepSeek V4 Flash); `QuestionEngine` (evidence-validated answers);
`DocumentGenerator.generate_cover_letter` + storage persistence; `mailer.py` (log/smtp providers);
`ApplicationRoute` (incl. `EMAIL` type with email field); the deterministic eligibility engine;
`Job.data_quality_flags`; immutable `Resume` rows + `CVTailoringSession.final_resume_id`;
Match Intelligence; `pdf_verifier`; frontend `ApplicationWorkflow`/`AppDetailPage`/
`CVTailoringWorkbench`; Telegram notifier; mocked-AI test conventions.

**Partially existed:** the package concept (Application carried `resume_id` + `cover_letter_path`
but no immutable multi-component package); approval (bound to run + profile version, not to
package versions); email (reset-only mailer, no generic provider or send records); cover letter
(not language/match-grounded, not versioned per package); QA + APPLICATION_EMAIL (tasks declared,
zero implementation); posting quality (intake flags only); work authorization (structured GCC
fields only).

**Missing:** `ApplicationPackage` + version locking; readiness summary; posting-quality signal;
work-auth detection; application email generation + recipient safety; QA service; approval↔package
binding; `EmailProvider.send` + send records; attachment validation; frontend review/compose UI.

## 2. Existing functionality reused (nothing rebuilt)

- **Approval system** — extended `ApplicationApproval` with nullable package-binding columns
  instead of creating a parallel approval table. Existing run-bound approvals are untouched.
- **State machine** — email sends map onto existing `ApplicationStatus` values
  (`SUBMITTING` → `APPLIED` / `SUBMISSION_BLOCKED` / `SUBMISSION_UNKNOWN`). No new states.
- **LLMTaskRouter** — all four AI tasks route through the existing router → heavy model
  (DeepSeek V4 Flash). No architecture change, no model substitution.
- **Resume versioning** — packages reference immutable `Resume` rows produced by the existing
  tailoring workbench (`finalize_session`).
- **Email config** — `email_provider.py` reuses the existing `settings.email` section
  (log/smtp providers, SecretStr credentials); no hardcoded credentials.
- **Storage** — attachment keys reuse the existing tenant-scoped storage-key conventions.
- **Phase 17 i18n** — language instructions reuse the established Arabic/English/bilingual
  prompt conventions and `dir="auto"` UI handling.
- **Test conventions** — new tests follow the existing in-memory-SQLite + tenant-context +
  mocked-LLM patterns (`conftest.py`).

## 3. New / modified models

**New:** `ApplicationPackage` (`models/application_package.py`) — immutable, versioned submission
package (see §4). Registered in `models/__init__.py`.

**Modified:** `ApplicationApproval` (`models/application.py`) — added nullable
`package_id` / `package_version` / `package_hash` columns. Existing approvals (which bind to
runs only) remain valid and untouched; the columns are nullable by design.

**New enums** (`models/enums.py`): `QAVerdict` (pass/warning/blocked), `PostingQualitySignal`
(likely_legitimate/needs_review/suspicious), `EmailSendState` (pending/sent/failed/unknown).

**Migration:** `20260907_c4f19a2b7d30_phase19_application_packages.py` — creates
`application_packages` + adds the three approval columns. Additive only; downgrade provided;
existing application records are not touched.

## 4. Application package design

`ApplicationPackage` is a row per immutable version of everything that would be submitted:

- Ownership: `application_id`, `job_id`, `route_id` (FK → `application_routes`)
- Components: `resume_id` (immutable Resume row), `cover_letter_key` + `cover_letter_text`
  (the exact reviewed text), `email_to`/`email_subject`/`email_body` (the exact approved email),
  `attachment_keys`, `answers` (snapshot), `language`
- Versioning: `version`, `content_hash` (SHA-256 over all components), `is_current`
- QA annotation: `qa_verdict`, `qa_issues`, `qa_model`
- Approval binding: `approval_id`, `approved_at`
- Send record: `send_state`, `sent_at`, `message_id`, `provider_response`, `sender_address`

Any component change creates a **new row** (`version + 1`) and marks the previous row
`is_current = False`; rows are never mutated (QA/approval/send fields are annotations, not
components). Identical input is idempotent — the same hash returns the existing package.

## 5. Version-locking behavior

`compute_content_hash()` is a SHA-256 over every component reference (route, resume, cover-letter
text, email to/subject/body, sorted attachment keys, answers, language). Approvals record
`(package_id, package_version, package_hash)` and the send path re-verifies the hash at send
time. Consequences, all covered by tests:

- A stale approval can never authorize a newer package: after any component change the new
  package has a different hash, and the old approval's hash can never match it
  (`test_stale_approval_cannot_send_newer_package`).
- The exact approved package is reproducible: old rows are immutable.
- Approval is idempotent per hash (re-approving returns the same approval).

## 6. Readiness UI

`GET /api/v1/applications/{id}/readiness` returns a concise summary answering "What remains
before I can apply?": `ready`, `missing` (e.g. tailored CV, cover letter, application email,
QA blockers), `warnings` (QA warnings, posting-quality signals, work-authorization status),
a per-document checklist, route, posting-quality signal, and work-authorization status.
The frontend `PackageReview` component renders this as a compact header (APPLICATION READY /
NOT READY YET + version + hash prefix) - deliberately not a large dashboard.

## 7. Cover-letter implementation

`services/package_generation.py::generate_package_cover_letter` - `LLMTask.COVER_LETTER` to
DeepSeek V4 Flash, grounded in job requirements + Match Intelligence summary + candidate
evidence + resume text + user-selected language. The system prompt hard-forbids inventing
experience, achievements, motivation, company facts, or credentials, and carries the
untrusted-data guard. Output is structured (`GeneratedCoverLetter`) and always goes through
human review before approval; storing it creates a new immutable package version.

## 8. Email generation

`generate_package_email` - `LLMTask.APPLICATION_EMAIL` to DeepSeek V4 Flash, producing
recipient/subject/body. Recipient safety: the model is instructed to echo the provided route
recipient and the service overwrites whatever recipient the model returned with the verified
route email - verified by `test_email_generation_ignores_model_recipient`, which feeds the
mock an attacker address and asserts the route address wins. The user sees the exact
TO / SUBJECT / BODY / ATTACHMENTS before approval; nothing is ever sent from an LLM callback.

## 9. Email execution / provider

`services/email_provider.py` - minimal `EmailProvider` interface with `LogEmailProvider`
(dev/CI; result explicitly marked as simulated acceptance so it can never be mistaken for
delivery evidence) and `SMTPEmailProvider` (real relay via existing `settings.email`; SMTP
send runs off the event loop in a worker thread; refused-recipient detection). No credentials
in source; resolution via `get_email_provider()`.

`services/package_send.py::send_package_email` enforces the safety sequence:
1. Package must be current, not already sent, and complete.
2. Approval must exist, be unused and unexpired, and match THIS package hash.
3. Attachments validated (section 13).
4. The approval is consumed and send_state=PENDING persisted BEFORE the provider is called.
5. Provider acceptance becomes SENT + Message-ID + provider response recorded; explicit
   failure becomes FAILED (app to SUBMISSION_BLOCKED); ambiguous exception becomes UNKNOWN
   (app to SUBMISSION_UNKNOWN). SENT means relay acceptance - delivery is never claimed
   without delivery evidence. Single-use: a second send of the same package is rejected.

## 10. Application answers

`generate_package_answers` - `LLMTask.APPLICATION_ANSWERS` to DeepSeek V4 Flash, grounded
strictly in candidate evidence. Answers carry ANSWERED / REVIEW_REQUIRED / UNKNOWN status +
confidence; the prompt forbids guessing and the structured schema enforces it. Stored as an
immutable snapshot on the package.

## 11. QA

`run_package_qa` - `LLMTask.APPLICATION_QA` to DeepSeek V4 Flash reviewing the complete
package (wrong company/title/recipient/attachment, unsupported claims, inconsistent dates,
stale or missing documents, incorrect route, suspicious posting signals, Arabic quality,
keyword stuffing). Deterministic pre-checks run first (missing resume/cover letter/recipient
are blockers) and any blocker issue forces BLOCKED regardless of the LLM verdict; an LLM
failure degrades to WARNING, never a false PASS. Verdicts: pass (proceed) / warning (user
must review) / blocked (cannot approve until fixed) - enforced in `approve_package`.

## 12. Approval behavior

`approve_package` reuses the existing single-use `ApplicationApproval` (24h expiry,
idempotent per package hash) and binds it to (package_id, package_version, package_hash).
Rules: only the CURRENT package can be approved; QA-BLOCKED packages cannot be approved
(`test_qa_blocked_package_cannot_be_approved`); a verified recipient must exist. If any
material component changes afterwards, a new package version is created and the old approval
can never match it - stale approvals cannot submit newer documents (section 5).

## 13. Attachment validation

`validate_attachments` enforces attachment safety before any send: every attachment key must
be one of the package own approved component keys (a newer/unapproved CV can never be
attached by accident - `test_validate_attachments_rejects_foreign_attachment`), the package
must have attachments at all, and the package resume version must be among them
(`test_validate_attachments_rejects_missing_resume`).

## 14. Arabic / bilingual behavior

Phase 17 conventions are reused: every generation prompt carries a language instruction
(Arabic keeps technical terms, URLs, emails, numbers, and proper nouns in English; mixed
mirrors the posting language mix). The frontend `PackageReview` and the email/cover-letter
review blocks use `dir="auto"` so Arabic content renders with correct RTL/bidi. The package
records its `language`, which is part of the content hash (changing language creates a new
version). Arabic/bilingual generation paths are exercised with mocked AI per the
credit-protection strategy.

## 15. Tests / results

All AI is mocked in tests - zero DeepSeek/Nemotron credit spend. 25 package tests:

- Unit (`tests/unit/test_phase19_packages.py`, 17): content-hash determinism + change
  sensitivity per component; package creation/immutability/idempotency; readiness missing and
  ready paths; posting quality (SUSPICIOUS on fee requests, NEEDS_REVIEW on free-mail
  destination); work authorization (explicit restriction detected, UNKNOWN stays UNKNOWN);
  approval binding + idempotency; QA-BLOCKED approval rejection; attachment validation
  (foreign attachment, missing resume); server-derived resume attachments; cross-job route
  rejection; send requires approval; send success records SENT + single-use;
  stale-approval protection.
- Integration (`tests/integration/test_phase19_packages_api.py`, 8): mocked cover-letter
  generation; recipient-safety override; mocked answers (ANSWERED + UNKNOWN); QA BLOCKED via
  deterministic pre-checks even when the mock LLM says PASS; QA PASS with components present;
  API package creation + readiness; client storage-key rejection; unauthorized access blocked
  (401/403).

Results: 25/25 passing. Regression suites re-run after lint fixes:
test_applications_api + test_migrations + test_models = 24 passed, 1 skipped (pre-existing
skip). App imports cleanly (14 router-level routes). Frontend production build passes.
Ruff: 15 auto-fixes applied to the new files (import order, newlines, datetime-UTC); the
remaining findings (E501 long lines, B904) match the pervasive style of the existing codebase
(118 similar findings in three legacy service files alone) and were left to match project
conventions.

## 16. Browser acceptance

COMPLETED in local development with deterministic mock AI. From the normal Applications
detail route, the walkthrough created a package, auto-selected the job-tailored CV, reviewed
the job and match context, generated and displayed the cover letter, application email, and
answers, ran QA, displayed readiness warnings, and approved the package. The UI confirmed
that version 4 and hash prefix `50f5e3f73d` were the exact approved snapshot. Mock mode
visibly disabled the send action; no email was sent. The four temporary package versions and
their approval were removed after acceptance, with zero matching rows verified afterward.

## 17. Real AI validation

DEFERRED. No DeepSeek credits were spent. Per the budget strategy, the controlled final
DeepSeek sample (cover letter + application email + QA, without sending) was not run - it
should be executed only at final acceptance with credits present and with explicit
authorization. All deterministic behavior is verified via mocks.

## 18. Deferred items

- Controlled real-DeepSeek validation sample (section 17).
- Real SMTP send (requires EMAIL__PROVIDER=smtp + credentials; log provider is the default).
- Cover-letter PDF rendering into storage for the package (the package stores the reviewed
  text + key; the existing DocumentGenerator render path can be wired when the review UX
  settles).
- Email EDIT action in the UI (regenerate is wired; manual edit creates a new version via the
  same POST /package endpoint but has no dedicated compose form yet).
- The 26 remaining ruff style findings in the new files (E501/B904), consistent with existing
  codebase style.

## 19. Remaining risks

- Approval `candidate_profile_version` is still hardcoded to 1 in package approvals (matching
  the existing FIXME in `SubmissionService.approve_application`); real profile versioning
  needs a candidate-profile version counter that does not exist yet.
- `_ensure_prep_run` creates a synthetic completed run when no preparation run exists, to
  satisfy the existing non-nullable `application_run_id` FK - a schema-level relaxation
  (nullable FK) would be cleaner but would touch existing migration semantics.
- Attachment bytes are not yet loaded from storage in `send_package_email` (keys are
  validated; the SMTP provider accepts attachment tuples, and the storage read can be wired
  when a real send is authorized). The log provider path is fully functional.
- QA LLM failure degrades to WARNING, which still allows approval - intentional (deterministic
  blockers still force BLOCKED), but worth revisiting if QA reliability matters more than
  availability.
- Posting-quality and work-authorization signals are heuristic - they are advisory warnings
  in readiness, never hard blocks, per the phase spec (a signal, not a verdict).

## 20. Phase 19.5 corrective acceptance

### Root cause and data flow

The corrupt tailored-CV failure had three independent causes along the live path:

1. Uploaded PDF text was positional rather than clean prose: letter-spaced headings,
   mojibake bullets, split header fragments, glued section names, and fused sentence
   boundaries. The legacy builder only recognized exact headers and hard-coded projects to
   an empty list, so most source material never reached the structured document.
2. The modern HTML template expected obsolete keys (`experiences`, `job_title`,
   `company_name`, and start/end dates), while the canonical schema emits `experience` with
   `title`, `company`, `duration`, and `description`. It rendered only a summary, experience,
   and skills, dropping identity/contact, projects, education, and certifications.
3. `PDFRenderer` pointed at WeasyPrint, which requires native GTK libraries not present in
   the Windows environment. The generator tolerated the per-format exception, so a DOCX
   could make the operation appear successful even though no PDF was produced.

The repaired flow is now:

`uploaded PDF/DOCX -> normalize_resume_text -> build_resume_data_from_text ->
TailoredResumeData -> accepted-change merge -> structured HTML/DOCX render ->
verify_pdf_document -> persisted tailored Resume -> application package resume_id`

### Corrective changes

- Normalization repairs bullet mojibake, letter-spaced and fragmented headers, glued major
  headers, and fused sentence boundaries while preserving dotted technology names.
- Structured parsing preserves summary, experience, projects, skills, education, and
  certifications; leading bullet markers are removed before list rendering.
- DOCX and HTML renderers consume the same canonical schema. The modern PDF layout now
  contains name/title/contact plus every populated major section with distinct block-level
  spacing and page-break-safe entries.
- PDF generation now uses the existing Playwright/Chromium dependency as the portable
  default; WeasyPrint remains available explicitly for legacy callers. A missing PDF is a
  hard failure in the end-to-end regression.
- The verifier checks candidate identity, expected sections, accepted and rejected changes,
  concatenation artifacts, non-sparse text, sane page count, and base-content retention.
- The application-package API resolves attachment keys from the authenticated user's Resume
  row. The browser never supplies arbitrary storage keys.
- The Phase 19 migration now gives `created_at` and `updated_at` database-side
  `CURRENT_TIMESTAMP` defaults. This was found by browser acceptance because ORM-only test
  table creation had masked the migration defect; downgrade/upgrade and live schema defaults
  were verified.
- The normal job, tailoring, workflow, and application-detail routes now converge on the
  review screen. The latest verified tailored CV is selected automatically, and the UI shows
  job context, match score, CV, letter, email, attachments, answers, QA, warnings, version,
  hash, and approval binding.
- Development mock AI is opt-in and Vite-development-only. It covers letter, email, answers,
  and QA while removing the send button; production behavior and providers are unchanged.

### Verification results

- Backend corrective/package/regression selection: **75 passed**, 2 non-failing dependency
  warnings. AI was mocked throughout.
- Frontend review/discoverability/tailoring selection: **7 passed**; job-card entry point:
  **1 passed** (5 unrelated tests skipped by name filter).
- Frontend production build: passed (`tsc && vite build`).
- Migration: Alembic at `c4f19a2b7d30 (head)`; both timestamp columns report
  `CURRENT_TIMESTAMP` defaults in SQLite.
- Visual artifact inspection: the representative output is one A4 page with all major
  sections, readable hierarchy and spacing, and no clipping, overlaps, duplicated bullets,
  or visible concatenation defects. The DOCX structure/content was inspected with
  `python-docx`; LibreOffice was unavailable in the bundled runtime, so DOCX-to-image visual
  rendering was not claimed.
- `git diff --check`: clean after whitespace correction.

No DeepSeek credits were used, no external application was submitted, and no email was sent.
