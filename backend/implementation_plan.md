# Implementation Plan: Decoupling Opportunity Discovery & Application Routing

This plan refactors the job discovery pipeline to separate "where a job was found" (OpportunitySource) from "how to apply for it" (ApplicationRoute). This allows ingesting jobs from ANY source (Telegram, WhatsApp, manual text) while standardizing how they flow into the application pipeline.

## Goal Description
Implement an ingestion layer that abstracts away the source of a job, normalizes it using LLMs (when unstructured), and uses a dedicated `ApplicationRouteResolver` to determine the correct ATS or email routing method independently of the discovery source.

## Proposed Changes

### Database Models

#### [MODIFY] `backend/app/models/job.py`
Extend the existing `Job` model to include provenance and ingestion metadata:
- `source_type`: `Mapped[str | None]` (e.g., "manual", "telegram", "workable", "web_search")
- `source_reference`: `Mapped[str | None]`
- `raw_text`: `Mapped[str | None] = mapped_column(Text)` (Crucial for auditability of unstructured pastes)
- `received_at`: `Mapped[datetime | None]`

#### [NEW] `backend/app/models/application_route.py`
Create the `ApplicationRoute` model linked to `Job` (1-to-1):
- `id`, `created_at`, `updated_at`, `user_id`
- `job_id`: ForeignKey to `jobs.id`
- `route_type`: `Mapped[str]` (WORKABLE, GREENHOUSE, LEVER, EMAIL, COMPANY_WEBSITE, LINKEDIN, MANUAL)
- `url`: `Mapped[str | None]`
- `email`: `Mapped[str | None]`
- `instructions`: `Mapped[str | None] = mapped_column(Text)`
- `confidence`: `Mapped[float]` (0.0 to 1.0)
- `requires_human`: `Mapped[bool]`
- `resolved_at`: `Mapped[datetime]`

### Core Abstractions

#### [NEW] `backend/app/core/job_discovery/opportunity_source.py`
Define the `OpportunitySource` interface:
- `ingest(data: Any) -> List[Dict[str, Any]]`
- `normalize(raw: Dict[str, Any]) -> Dict[str, Any]`
- `health_check() -> bool`

Create concrete providers:
- `ManualProvider` (for parsing unstructured text via LLM)
- `WorkableProvider`, `GreenhouseProvider`, `LeverProvider` (adapters for existing ATS scrapers)
- `TelegramProvider` / `WhatsAppProvider` (stubs for future use)

#### [NEW] `backend/app/core/job_discovery/application_route_resolver.py`
Implement `ApplicationRouteResolver`:
Takes a `Job` as input and returns an `ApplicationRoute`.
Resolution priority:
1. Explicit application URL in posting (ATS detection without scraping)
2. Explicit email address extraction (using LLM if terms like "send CV to" are present)
3. Explicit application instructions
4. Known ATS URL pattern fallback
5. Manual human resolution (If confidence < 0.8, flag `requires_human=True`)

### LLM Integration

#### [NEW] `backend/app/core/llm/prompts/opportunity_extraction.py`
Prompt to parse unstructured job text (WhatsApp/Telegram/Manual paste) into strict canonical JSON (title, company, description, location, application_url, email).

#### [NEW] `backend/app/core/llm/prompts/route_extraction.py`
Prompt to extract application instructions or email routing (e.g., "send CV to hr@company.com with subject X") from job descriptions.

### API & Services

#### [MODIFY] `backend/app/api/v1/opportunities.py` (New or extended from jobs.py)
Add `POST /api/v1/opportunities/ingest`:
Accepts `{"text": "...", "source_type": "manual|whatsapp|...", "source_reference": null}`.
- Invokes `ManualProvider.ingest()` which calls the LLM extraction pipeline.
- Saves the `Job` with provenance.
- Runs eligibility & matching.
- Runs `ApplicationRouteResolver`.

#### [MODIFY] `backend/app/services/discovery_service.py` (Orchestrator)
Refactor `DiscoveryService` to act as the `DiscoveryOrchestrator`, capable of loading various `OpportunitySource` providers, running ingestion, and delegating to the `ApplicationRouteResolver` before preparation.

## Verification Plan

### Automated Tests
Create `backend/tests/unit/test_ingestion.py`:
- Test manual pasted job text parses correctly via LLM.
- Test email application instruction extraction via resolver.
- Test ATS detection from explicit Workable/Greenhouse URLs without page scraping.
- Test provenance fields (`raw_text`, `source_type`) are preserved.
- Test low-confidence routes get flagged with `requires_human=True`.

### Manual Verification
- Send a POST request to `/api/v1/opportunities/ingest` with a mocked WhatsApp job post ("Hiring software engineer at ACME. Send CV to jobs@acme.com") and verify the `Job` and `ApplicationRoute` (EMAIL) are created properly.
