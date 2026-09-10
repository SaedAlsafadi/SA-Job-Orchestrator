# Phase 20A.3 — Operational UX Completion

Date: 2026-09-10

## Outcome

Phase 20A.3 is complete. Dashboard dismissal is persistent and version-aware, résumé preview/archive/revision paths are operational, opportunity cards expose one state-derived primary action, application routes are explained honestly, and the real browser path reached Application Review without enabling live submission.

## 1. Dashboard data-source architecture

- **Action Needed** is derived from the tenant-scoped Applications endpoint. The dashboard includes `pending_review`, `queued`, `failed`, `waiting_for_review`, and `submission_blocked` applications.
- **Recently Active** is derived from the same Applications response and contains the remaining recent application states.
- **Status badges** are presentation metadata mapped directly from `Application.status`; dismissal never changes this value.
- **Dashboard KPIs** come from the analytics overview endpoint, independently of feed dismissal.
- **Interventions** remain the existing WebSocket/store plus Redis rendezvous flow used by the global intervention modal; they were not duplicated into a new notification system.
- **Transient UI notifications** remain the existing toaster store. Telegram `NotificationLog` is outbound-delivery/deduplication history and has no user read/dismiss semantics, so it was not suitable for dashboard feed state.
- The analytics activity timeline remains an analytics data source and is not the source of the dashboard's Recently Active cards.

## 2. Dismissal, persistence, and resurfacing

A minimal `dashboard_dismissals` model and API were added because no existing user-readable notification abstraction fit dashboard semantics. Each row stores `user_id`, `entity_type`, `entity_id`, `fingerprint`, and `dismissed_at`.

The fingerprint is derived from application status plus `updated_at`. Dismissal therefore hides only the current material version. A later status/update produces a new fingerprint and resurfaces the item while preserving the old audit record and the underlying workflow state.

Individual Dismiss controls and Clear recent activity are non-destructive. Empty feeds show the accepted caught-up and no-activity states.

## 3. Résumé preview, archive, and revision

- Preview source order is canonical structured `content_text`, then structured sections, then plain text only as fallback. Existing PDF/DOCX artifacts remain downloadable.
- Desktop layout provides a wide, scrollable A4-like document pane with identity, summary, experience, projects, education, skills, certifications, and canonical raw content where available.
- Card thumbnails now use real document content rather than decorative stripes.
- Archive is implemented with nullable `archived_at`. Active list queries exclude archived résumés by default. No destructive résumé delete was introduced, so Applications, ApplicationPackages, approvals, tailoring sessions, and historical artifacts retain valid references.
- Revise resolves the session that produced a tailored résumé. For legacy tailored résumés that predate session tracking, it creates an idempotent, model-free review session using the selected immutable tailored version as its source. Finalization creates a new Resume/version and never overwrites the selected version.

## 4. Tailoring preview

The real workbench now renders both Original and Draft from canonical résumé content. Existing changes are merged into Draft deterministically. With zero changes, both previews remain populated and the workbench shows: “No tailoring suggestions have been generated yet.”

## 5. Opportunity action policy

The jobs API now supplies one `operational_state` assembled from related match data, the latest tailoring session, verified tailored artifacts, Application, current ApplicationPackage, approval, and ApplicationRoute. The frontend resolver uses that object and returns exactly one primary next action.

Legacy database match scores are normalized once at the API boundary from 0–100 storage to the canonical 0–1 Job payload. The UI then performs the single display conversion to 0–100.

### Real-data audit

| Job ID | Stored job state | Match | Tailoring | Application | Package | Route | Browser CTA |
|---|---|---|---|---|---|---|---|
| `cdda8c9feb4f499ea55c99be98a9968b` | processing | none | none | none | none | — | Processing… (disabled) |
| `4eea6061b6624110bd7fe1ef9b263b28` | new/ready | none | none | none | none | — | Analyze Match |
| `b815b95701a642a79594bb5108924361` | new/ready | present | none | none | none | — | Tailor CV |
| `c612641b985e4d74a2246c3bfc875ff4` | new/ready | present, 51 | none | none | none | — | Tailor CV |
| `c3745bc2073b49dab7e73c3f7f636d82` | new/ready | none | none | pending_review | v1 incomplete | — | Continue Preparation |
| `74c8a9a25e5c4b1ca5a59ed5ec6061b9` | new/ready | not scored | verified session + résumé | pending_review | v2 ready | MANUAL | Review Application |

The last record was also exercised through its real lifecycle during acceptance: Continue Tailoring → verified résumé/Prepare Application → pending application → ready package/Review Application.

The score regression cards rendered `47`, `51`, `45`, `32`, and `27` in the browser—not `4700`, `5100`, `4500`, `3200`, or `2700`.

## 6. Application-route UX

Package review presents route-specific next-step copy for EMAIL, WORKABLE, GREENHOUSE, LEVER, COMPANY_WEBSITE, LINKEDIN, and MANUAL. Legacy jobs without route records receive a deterministic fallback at package time: explicit application URLs become COMPANY_WEBSITE; otherwise the route is honestly marked MANUAL. No LLM or paid model is needed for this fallback.

Live browser proof showed `MANUAL — Review the package and follow the application instructions manually.` Submission remained disabled.

## 7. Manual browser acceptance

- Dismissed an Action Needed item, confirmed immediate disappearance, refreshed, and confirmed persistence.
- Opened the dismissed item's Application and confirmed its `Pending review` status was unchanged.
- Dismissed the remaining attention/activity cards and confirmed both accepted empty states persisted after refresh.
- Selected a base résumé and a tailored résumé; both showed full canonical document content.
- Clicked Revise on a legacy tailored résumé and reached a real workbench session.
- Verified populated Draft and Original panels and the zero-suggestions message.
- Archived an unneeded duplicate tailored résumé and confirmed the active list changed from five to four after refresh.
- Verified Processing, Analyze Match, Tailor CV, Continue Preparation, and Review Application card states on current database records.
- Verified card score rings `47`, `51`, `45`, `32`, and `27`.
- Clicked a matched opportunity into its tailoring entry without exposing a competing Prepare action.
- Completed a real local path through revision/finalization, Prepare Application, package creation, and Review Application.
- No external application was submitted.

Acceptance artifacts created by this local validation are session `444cf984209c48ab988677f2def8aec9`, immutable résumé `fe3ddf6662694cf4b451198e0744d6dd`, application `8716f0f632494529b3e170e1d75b16c6`, and package `pkg_29a37ad3cb9e` v2. Archived duplicate résumé: `228019deb2b743e79793271a3aaac133`.

## 8. Verification

- Frontend: **33 test files, 145 tests passed**.
- Backend focused operational/package/tailoring/migration suite: **57 passed, 1 skipped, 1 expected failure**.
- TypeScript: `tsc --noEmit` passed.
- Production build: passed (`vite build`, 239 modules). Vite reports the existing advisory that the main bundle is slightly above 500 kB; this is not a build failure.
- Alembic: upgraded local acceptance database from `c4f19a2b7d30` to `d20a3f01`.

## 9. Constraints preserved

No branding direction, LLM routing, Redis/Arq architecture, or live-submission setting was changed. Preview, archive, revision navigation, dashboard dismissal, CTA resolution, route explanation, and original-CV rendering all operate without a paid AI model.
