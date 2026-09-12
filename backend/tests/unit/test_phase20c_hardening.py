"""Phase 20C deterministic reliability and route-workflow regressions."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.application import Application
from app.models.application_route import ApplicationRoute
from app.models.enums import ApplicationStatus
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.matching import (
    EvidenceType,
    RequirementAnalysis,
    RequirementImportance,
    RequirementStatus,
)
from app.services.application import confirm_manual_submission, record_external_route_opened
from app.services.application_package import create_or_update_package
from app.services.matching import _direct_skill_matches, _ensure_requirement_coverage, score_requirement_analysis
from app.services.package_facts import (
    build_protected_facts,
    date_future_status,
    llm_issue_overruled,
    protected_entity_issues,
    restore_protected_entities,
)
from app.services.package_generation import QAIssue, _email_sanity_error
from app.services.package_send import approve_package
from tests.conftest import TEST_USER_ID


def requirement(key: str, evidence: EvidenceType, importance=RequirementImportance.HIGH):
    status = RequirementStatus.MATCH if evidence == EvidenceType.DIRECT else (
        RequirementStatus.PARTIAL if evidence in {EvidenceType.TRANSFERABLE, EvidenceType.WEAK}
        else RequirementStatus.GAP
    )
    return RequirementAnalysis(
        requirement_id=key,
        original_text=key,
        normalized_requirement=key,
        category="CORE_RESPONSIBILITY",
        importance=importance,
        status=status,
        evidence_type=evidence,
        explanation="fixture",
    )


def test_completed_june_2026_range_is_not_future():
    assert date_future_status("JUNE 2026", today=date(2026, 9, 12)) == "NOT_FUTURE"
    issue = QAIssue(
        kind="future_date",
        detail="FEB 2022 - JUNE 2026 is in the future",
        severity="warning",
    )
    assert llm_issue_overruled(issue, {"degrees": []}) is True


def test_supported_degree_warning_is_overruled():
    issue = QAIssue(kind="unsupported_claim", detail="I hold a B.Sc. is unsupported", severity="warning")
    assert llm_issue_overruled(issue, {"degrees": ["Bachelor of Science (B.Sc.)"]}) is True


def test_resume_spelling_is_a_protected_fact():
    facts = build_protected_facts(
        {"experience": [{"company": "Minnha IT"}]},
        "TECHNOLOGY OPERATIONS — MINNHA IT",
    )
    assert facts["employers"] == ["MINNHA IT"]
    issues = protected_entity_issues(["My work at Minnah IT improved workflows."], facts)
    assert issues and issues[0]["kind"] == "protected_entity_changed"


def test_near_match_name_is_restored_without_inserting_absent_entity():
    facts = {"employers": ["Minnha IT"], "candidate_names": ["Saed Alsafadi"]}
    restored = restore_protected_entities("I improved workflows at Minha IT.", facts)
    assert restored == "I improved workflows at Minnha IT."
    assert "Saed Alsafadi" not in restored


def test_relative_match_calibration_orders_direct_transferable_weak():
    strong = score_requirement_analysis([requirement("a", EvidenceType.DIRECT), requirement("b", EvidenceType.DIRECT)])
    moderate = score_requirement_analysis([requirement("a", EvidenceType.TRANSFERABLE), requirement("b", EvidenceType.DIRECT)])
    weak = score_requirement_analysis([requirement("a", EvidenceType.WEAK), requirement("b", EvidenceType.NONE)])
    blocked = score_requirement_analysis([requirement("a", EvidenceType.DIRECT), requirement("b", EvidenceType.NONE, RequirementImportance.CRITICAL)])
    assert strong > moderate > weak
    assert blocked < strong


def test_match_explanation_covers_every_source_requirement():
    analysis = [requirement("Python automation", EvidenceType.DIRECT)]
    _ensure_requirement_coverage(
        analysis,
        "\\- Python automation\n\n\\- Ericsson Packet Core Management\n\n\\- ITIL preferred",
    )
    assert [item.original_text for item in analysis] == [
        "Python automation", "Ericsson Packet Core Management", "ITIL preferred",
    ]
    assert analysis[1].evidence_type == EvidenceType.NONE
    assert analysis[2].importance == RequirementImportance.LOW
    assert analysis[2].category == "PREFERRED"


def test_canonical_skill_names_receive_direct_credit():
    req = requirement("RESTful APIs and React.js", EvidenceType.NONE)
    candidate = SimpleNamespace(skills=[
        SimpleNamespace(name="REST APIs", evidence_id="skill-rest"),
        SimpleNamespace(name="React", evidence_id="skill-react"),
        SimpleNamespace(name="and workflow automation", evidence_id="fragment"),
    ])
    assert _direct_skill_matches(req, candidate) == ["skill-rest", "skill-react"]


def test_application_email_length_and_cover_overlap_guards():
    assert "too long" in _email_sanity_error("word " * 171, None)
    cover = "I build reliable Python automation and data workflows for business teams."
    assert "duplicates" in _email_sanity_error(cover, cover)
    assert _email_sanity_error(
        "Hello, I am applying for the role. My Python automation experience is relevant. "
        "Please find my CV attached. Kind regards, Saed.",
        "A detailed narrative about research, operations, university admissions, and projects.",
    ) == ""


async def _approved_website_application(db_session):
    job = Job(
        user_id=TEST_USER_ID, platform="manual", platform_job_id="phase20c-job",
        title="Engineer", company="Example", url="https://example.com/job", status="ready",
    )
    resume = Resume(user_id=TEST_USER_ID, name="CV", type="tailored", template_id="modern")
    db_session.add_all([job, resume])
    await db_session.flush()
    app = Application(
        user_id=TEST_USER_ID, job_id=job.id, resume_id=resume.id,
        status=ApplicationStatus.READY, apply_mode="review",
    )
    route = ApplicationRoute(
        user_id=TEST_USER_ID, job_id=job.id, route_type="COMPANY_WEBSITE",
        url=job.url, is_preferred=True, resolved_at=datetime.now(UTC),
    )
    db_session.add_all([app, route])
    await db_session.commit()
    package = await create_or_update_package(
        db_session, app.id, TEST_USER_ID, route_id=route.id, resume_id=resume.id,
        cover_letter_text="Letter", email_to="legacy@example.com",
        email_subject="Legacy", email_body="Legacy email",
    )
    await approve_package(db_session, app.id, package.id, TEST_USER_ID)
    return app, package


@pytest.mark.asyncio
async def test_company_website_package_strips_email_and_records_honest_manual_submission(db_session):
    app, package = await _approved_website_application(db_session)
    assert package.email_to is None and package.email_subject is None and package.email_body is None

    await record_external_route_opened(db_session, app.id)
    applied = await confirm_manual_submission(db_session, app.id)

    assert applied.status == ApplicationStatus.APPLIED
    assert applied.audit_metadata["submission_method"] == "USER_CONFIRMED"
    assert applied.audit_metadata["submission_verification"] == "MANUAL"
    assert [e["event"] for e in applied.audit_metadata["timeline"]] == [
        "USER_OPENED_APPLICATION", "USER_CONFIRMED_SUBMITTED"
    ]
