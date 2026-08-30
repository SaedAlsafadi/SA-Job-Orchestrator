# Walkthrough: Phase 12 - Autonomous Discovery Engine

## Changes Made
1. **Database Schema**: Transitioned from URL-based monitoring to Strategy-based discovery.
    - Created `SearchProfile` (Strategy) and `CompanyWatch` (Targeted URLs) models to replace `MonitoringSchedule`.
    - Created `DiscoveryRun` and `DiscoveryEvent` to track execution and job provenance.
    - Added immutable provenance fields (`source_type`, `content_hash`, `first_seen_at`) and relationships to the `Job` model.
    - Applied Alembic migrations successfully.
2. **Provider Abstractions**: Built a generic interface for discovering jobs.
    - Defined `DiscoveryProvider` and `ProviderCapabilities` (`global_search`, `company_search`, `direct_url`).
    - Implemented `ExaDiscoveryProvider` for global web search.
    - Wrapped existing connectors into `WorkableProvider`, `GreenhouseProvider`, and `LeverProvider`.
3. **Query Planner**: Built `QueryPlanner` to deterministically generate a bounded (max 15) and deduplicated set of search queries per cycle (e.g. `Software Engineer Remote`).
4. **Discovery Orchestrator**: Built the central autonomous pipeline `DiscoveryOrchestrator` (`backend/app/services/discovery/orchestrator.py`).
    - **Fan-out**: Executes queries across capable providers.
    - **Canonicalization & Deduplication**: Canonicalizes URLs and hashes job content, deduplicating against the database (ensuring no re-preparations).
    - **Deterministic Filters**: Performs cheap pre-filtering (Title/Location match).
    - **Match & Shortlist**: Passes eligible jobs to `CandidateJobMatcher` (LLM Qualitative Shortlist).
    - **Ranking**: Ranks jobs based on `match_score` and freshness.
    - **Limits**: Respects `max_preparations_per_cycle` and `max_preparations_per_day`.
    - **Queueing**: Hands off to the Arq preparation queue safely (`prepare_application_run`).
5. **CLI & Testing**:
    - Updated `scripts/run_monitoring.py` to use `--once --dry-run` and print a detailed rich table of stats.
    - Wrote extensive unit tests in `test_discovery_orchestrator.py` which pass successfully.

## Validation Results
- **Schema & Migrations**: Ran `alembic upgrade head`, database schema updated smoothly.
- **Provider Fan-out**: Verified via tests and CLI dry-run that queries are planned, distributed, and gracefully fail-safe when providers are unavailable (e.g., missing API keys).
- **CLI Explainability**: `python scripts/run_monitoring.py --once --dry-run` outputs detailed cycle statistics and reasons for skips (e.g., "daily preparation capacity reached", "failed eligibility check").
- **Pipeline Unit Tests**: Tested the query planner's deduplication and cartesian product bounds, partial provider failures, and daily queue caps logic; all tests passed.
