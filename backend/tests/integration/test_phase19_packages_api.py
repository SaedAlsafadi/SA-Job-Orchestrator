"""Phase 19 package API integration tests — all AI mocked; no LLM calls."""

from __future__ import annotations

import pytest

from app.models.application import Application
from app.models.enums import ApplicationStatus, QAVerdict
from app.models.job import Job
from app.models.resume import Resume
from app.services.package_generation import (
    GeneratedAnswers,
    GeneratedApplicationEmail,
    GeneratedCoverLetter,
    QAIssue,
    QAResult,
)
from app.services.package_generation import (
    generate_package_answers,
    generate_package_cover_letter,
    generate_package_email,
    run_package_qa,
)

from tests.conftest import TEST_USER_ID, TEST_DATABASE_URL  # noqa: F401


async def _seed(db_session) -> tuple[Job, Application]:
    job = Job(
        user_id=TEST_USER_ID,
        platform="manual",
        platform_job_id="j-1",
        title="Senior Python Developer",
        company="TechCorp Inc.",
        location="Riyadh",
        url="https://example.com/jobs/1",
        description="Senior Python Developer role with FastAPI and cloud work. " * 4,
        status="new",
    )
    db_session.add(job)
    await db_session.flush()
    app = Application(user_id=TEST_USER_ID, job_id=job.id, status=ApplicationStatus.READY)
    db_session.add(app)
    await db_session.commit()
    return job, app


class FakeRouter:
    """Deterministic stand-in for LLMTaskRouter (no network)."""

    def __init__(self, cover=None, email=None, answers=None, qa=None):
        self.cover = cover
        self.email = email
        self.answers = answers
        self.qa = qa
        self.calls: list[str] = []

    async def complete_with_structured_output(self, task, prompt, output_schema, system_prompt=""):
        self.calls.append(str(task.value))
        if "cover_letter" in str(task.value):
            return self.cover
        if "application_email" in str(task.value):
            return self.email
        if "application_answers" in str(task.value):
            return self.answers
        if "application_qa" in str(task.value):
            return self.qa
        raise AssertionError(f"unexpected task {task}")


@pytest.mark.asyncio
async def test_cover_letter_generation_mocked(db_session):
    job, app = await _seed(db_session)
    fake = FakeRouter(cover=GeneratedCoverLetter(subject_line="Application", body="Dear hiring team..."))
    result = await generate_package_cover_letter(db_session, app.id, TEST_USER_ID, fake)
    assert result.body == "Dear hiring team..."
    assert "cover_letter" in fake.calls


@pytest.mark.asyncio
async def test_email_generation_ignores_model_recipient(db_session):
    """Recipient safety: the model's recipient is overridden by the verified route."""
    job, app = await _seed(db_session)
    fake = FakeRouter(
        email=GeneratedApplicationEmail(
            recipient="attacker@evil.example",
            subject="Application",
            body="Please consider me.",
        )
    )
    result = await generate_package_email(
        db_session, app.id, TEST_USER_ID, fake,
        route_email="jobs@techcorp.com", cover_letter_text=None,
    )
    assert result.recipient == "jobs@techcorp.com"


@pytest.mark.asyncio
async def test_answers_generation_mocked(db_session):
    job, app = await _seed(db_session)
    fake = FakeRouter(
        answers=GeneratedAnswers(answers=[])
    )
    from app.services.package_generation import GeneratedAnswer

    fake.answers = GeneratedAnswers(
        answers=[
            GeneratedAnswer(question="Years of Python?", answer="6", status="ANSWERED", confidence=0.9),
            GeneratedAnswer(question="Willing to relocate?", answer="", status="UNKNOWN", confidence=0.0),
        ]
    )
    result = await generate_package_answers(
        db_session, app.id, TEST_USER_ID, fake, questions=["Years of Python?", "Willing to relocate?"]
    )
    assert result.answers[0].status == "ANSWERED"
    assert result.answers[1].status == "UNKNOWN"


@pytest.mark.asyncio
async def test_qa_blocked_on_missing_components(db_session):
    """Deterministic pre-checks force BLOCKED even if the fake LLM says PASS."""
    job, app = await _seed(db_session)
    from app.models.application_package import ApplicationPackage
    from app.services.application_package import create_or_update_package

    pkg = await create_or_update_package(db_session, app.id, TEST_USER_ID)
    fake = FakeRouter(qa=QAResult(verdict=QAVerdict.PASS, issues=[]))
    result = await run_package_qa(db_session, pkg, fake)
    assert result.verdict == QAVerdict.BLOCKED
    assert any(i.severity == "blocker" for i in result.issues)


@pytest.mark.asyncio
async def test_qa_pass_when_components_present(db_session):
    job, app = await _seed(db_session)
    resume = Resume(
        user_id=TEST_USER_ID,
        name="Tailored",
        type="tailored",
        file_path_pdf="users/u/r.pdf",
        content_text="Python developer",
    )
    db_session.add(resume)
    await db_session.flush()
    from app.services.application_package import create_or_update_package

    pkg = await create_or_update_package(
        db_session, app.id, TEST_USER_ID,
        resume_id=resume.id,
        cover_letter_text="Dear team...",
        email_to="jobs@techcorp.com",
    )
    fake = FakeRouter(qa=QAResult(verdict=QAVerdict.PASS, issues=[]))
    result = await run_package_qa(db_session, pkg, fake)
    assert result.verdict == QAVerdict.PASS
    assert pkg.qa_verdict == QAVerdict.PASS


@pytest.mark.asyncio
async def test_api_create_package_and_readiness(client, db_session):
    job, app = await _seed(db_session)

    resp = await client.post(
        f"/api/v1/applications/{app.id}/package",
        json={"cover_letter_text": "Hello", "language": "en"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert body["is_current"] is True
    assert body["route_id"] is not None

    resp = await client.get(f"/api/v1/applications/{app.id}/readiness")
    assert resp.status_code == 200
    readiness = resp.json()
    assert readiness["ready"] is False
    assert "tailored CV" in readiness["missing"]
    assert readiness["route"] == "MANUAL"


@pytest.mark.asyncio
async def test_api_rejects_client_supplied_storage_keys(client, db_session):
    """Storage attachment references are resolved server-side, never trusted from UI."""
    _, app = await _seed(db_session)

    resp = await client.post(
        f"/api/v1/applications/{app.id}/package",
        json={"attachment_keys": ["users/other/private.pdf"]},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_unauthorized_access_blocked(anon_client, db_session):
    job, app = await _seed(db_session)
    resp = await anon_client.get(f"/api/v1/applications/{app.id}/readiness")
    assert resp.status_code in (401, 403)
