"""Phase 19 package unit tests — all AI mocked; no DeepSeek/Nemotron calls."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.application import Application
from app.models.application_route import ApplicationRoute
from app.models.enums import (
    ApplicationStatus,
    EmailSendState,
    PostingQualitySignal,
    QAVerdict,
)
from app.models.job import Job
from app.models.resume import Resume
from app.services.application_package import (
    PackageError,
    build_readiness,
    compute_content_hash,
    create_or_update_package,
)
from app.services.email_provider import LogEmailProvider, OutgoingEmail
from app.services.package_send import (
    approve_package,
    send_package_email,
    validate_attachments,
)
from app.services.posting_quality import assess_posting_quality
from app.services.work_authorization import detect_work_requirements

from tests.conftest import TEST_USER_ID


async def _make_job(db_session, **overrides) -> Job:
    data = {
        "user_id": TEST_USER_ID,
        "platform": "manual",
        "platform_job_id": "job-1",
        "title": "Senior Python Developer",
        "company": "TechCorp Inc.",
        "location": "Riyadh",
        "url": "https://example.com/jobs/1",
        "description": "We are looking for a Senior Python Developer with FastAPI "
        "experience. You will build backend services and APIs. " * 3,
        "status": "new",
    }
    data.update(overrides)
    job = Job(**data)
    db_session.add(job)
    await db_session.commit()
    return job


async def _make_application(db_session, job: Job, **overrides) -> Application:
    app = Application(user_id=TEST_USER_ID, job_id=job.id, status=ApplicationStatus.READY, **overrides)
    db_session.add(app)
    await db_session.commit()
    return app


async def _make_resume(db_session) -> Resume:
    resume = Resume(
        user_id=TEST_USER_ID,
        name="Tailored CV",
        type="tailored",
        file_path_pdf="users/u/resumes/r.pdf",
        file_path_docx="users/u/resumes/r.docx",
        content_text="Senior Python Developer with FastAPI experience.",
    )
    db_session.add(resume)
    await db_session.commit()
    return resume


async def _make_email_route(db_session, job: Job) -> ApplicationRoute:
    route = ApplicationRoute(
        user_id=TEST_USER_ID,
        job_id=job.id,
        route_type="EMAIL",
        email="jobs@techcorp.com",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(route)
    await db_session.commit()
    return route


# ---------------- content hash / version locking ----------------


def test_content_hash_changes_on_any_component_change():
    base = dict(
        application_id="app1",
        route_id="r1",
        resume_id="res1",
        cover_letter_text="letter",
        email_to="a@b.com",
        email_subject="s",
        email_body="body",
        attachment_keys=["k1"],
        answers=[],
        language="en",
    )
    h1 = compute_content_hash(**base)
    h2 = compute_content_hash(**base)
    assert h1 == h2  # deterministic
    for field, changed in [
        ("resume_id", "res2"),
        ("cover_letter_text", "letter v2"),
        ("email_to", "other@b.com"),
        ("email_subject", "s2"),
        ("email_body", "body2"),
        ("attachment_keys", ["k2"]),
        ("language", "ar"),
    ]:
        mutated = dict(base)
        mutated[field] = changed
        assert compute_content_hash(**mutated) != h1, field


@pytest.mark.asyncio
async def test_package_creation_and_immutability(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    resume = await _make_resume(db_session)

    pkg1 = await create_or_update_package(db_session, app.id, TEST_USER_ID, resume_id=resume.id)
    assert pkg1.version == 1 and pkg1.is_current

    # Identical input → same immutable package (idempotent)
    pkg_same = await create_or_update_package(db_session, app.id, TEST_USER_ID, resume_id=resume.id)
    assert pkg_same.id == pkg1.id and pkg_same.version == 1

    # Component change → NEW immutable version, old row not current
    pkg2 = await create_or_update_package(
        db_session, app.id, TEST_USER_ID, resume_id=resume.id, cover_letter_text="updated letter"
    )
    assert pkg2.id != pkg1.id
    assert pkg2.version == 2
    assert pkg2.content_hash != pkg1.content_hash
    assert pkg2.is_current


@pytest.mark.asyncio
async def test_package_derives_owned_resume_attachments(db_session):
    """The browser supplies a resume ID, never internal storage keys."""
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    resume = await _make_resume(db_session)

    pkg = await create_or_update_package(
        db_session, app.id, TEST_USER_ID, resume_id=resume.id
    )

    assert pkg.attachment_keys == [resume.file_path_pdf, resume.file_path_docx]


@pytest.mark.asyncio
async def test_package_rejects_route_from_another_job(db_session):
    """A caller cannot bind a route (and its recipient) from a different job."""
    job = await _make_job(db_session)
    other_job = await _make_job(
        db_session,
        platform_job_id="job-2",
        url="https://example.com/jobs/2",
    )
    app = await _make_application(db_session, job)
    route = ApplicationRoute(
        user_id=TEST_USER_ID,
        job_id=other_job.id,
        route_type="EMAIL",
        email="wrong@example.com",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(route)
    await db_session.commit()

    with pytest.raises(PackageError, match="route not found or unauthorized"):
        await create_or_update_package(
            db_session,
            app.id,
            TEST_USER_ID,
            route_id=route.id,
        )


@pytest.mark.asyncio
async def test_readiness_reports_missing_documents(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    pkg = await create_or_update_package(db_session, app.id, TEST_USER_ID)
    readiness = await build_readiness(db_session, pkg)
    assert readiness["ready"] is False
    assert "tailored CV" in readiness["missing"]
    assert "cover letter" in readiness["missing"]
    assert readiness["posting_quality"]["signal"] == PostingQualitySignal.LIKELY_LEGITIMATE.value
    assert readiness["work_authorization"]["status"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_readiness_ready_with_all_components(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    resume = await _make_resume(db_session)
    pkg = await create_or_update_package(
        db_session, app.id, TEST_USER_ID,
        resume_id=resume.id,
        cover_letter_text="Dear hiring manager...",
        attachment_keys=["users/u/resumes/r.pdf"],
    )
    readiness = await build_readiness(db_session, pkg)
    assert readiness["ready"] is True
    assert readiness["missing"] == []


# ---------------- posting quality ----------------


@pytest.mark.asyncio
async def test_posting_quality_suspicious_on_fee_request(db_session):
    job_data_desc = (
        "Great remote role! To start, please pay a small processing fee of $50 for "
        "application registration. Send your details via WhatsApp and we will proceed. "
        "This is a full-stack position with Python and React work. " * 2
    )
    job = await _make_job(db_session, description=job_data_desc)
    result = assess_posting_quality(job)
    assert result.signal == PostingQualitySignal.SUSPICIOUS


@pytest.mark.asyncio
async def test_posting_quality_needs_review_on_free_mail(db_session):
    job = await _make_job(
        db_session,
        company="unknown",
        description="Send your CV to hiring.person@gmail.com for this Python role. " * 4,
    )
    result = assess_posting_quality(job)
    assert result.signal == PostingQualitySignal.NEEDS_REVIEW


# ---------------- work authorization ----------------


def test_work_auth_explicit_restriction():
    text = "Candidates must have work authorization in Saudi Arabia. No sponsorship is provided for this role."
    result = detect_work_requirements(text)
    assert result.status == "RESTRICTED"
    assert "sponsorship_unavailable" in result.requirements


def test_work_auth_unknown_stays_unknown():
    result = detect_work_requirements("A great team in Riyadh with modern tooling.")
    assert result.status == "UNKNOWN"
    assert result.requirements == []


# ---------------- approval binding + stale-approval protection ----------------


@pytest.mark.asyncio
async def test_approval_binds_to_package_and_survives_idempotency(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    resume = await _make_resume(db_session)
    pkg = await create_or_update_package(
        db_session, app.id, TEST_USER_ID,
        resume_id=resume.id,
        email_to="jobs@techcorp.com",
        email_subject="Application",
        email_body="Hello",
        attachment_keys=["users/u/resumes/r.pdf"],
    )
    approval = await approve_package(db_session, app.id, pkg.id, TEST_USER_ID)
    assert approval.package_id == pkg.id
    assert approval.package_hash == pkg.content_hash
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.APPROVED

    # Idempotent: same hash → same approval
    again = await approve_package(db_session, app.id, pkg.id, TEST_USER_ID)
    assert again.id == approval.id


@pytest.mark.asyncio
async def test_company_website_package_can_be_approved_without_email_recipient(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    route = ApplicationRoute(
        user_id=TEST_USER_ID,
        job_id=job.id,
        route_type="COMPANY_WEBSITE",
        url="https://example.com/jobs/1",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(route)
    await db_session.commit()
    pkg = await create_or_update_package(
        db_session, app.id, TEST_USER_ID, route_id=route.id
    )

    approval = await approve_package(db_session, app.id, pkg.id, TEST_USER_ID)

    assert approval.package_id == pkg.id
    assert approval.platform == "company_website"


@pytest.mark.asyncio
async def test_company_website_package_cannot_use_email_send(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    route = ApplicationRoute(
        user_id=TEST_USER_ID,
        job_id=job.id,
        route_type="COMPANY_WEBSITE",
        url="https://example.com/jobs/1",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(route)
    await db_session.commit()
    pkg = await create_or_update_package(
        db_session,
        app.id,
        TEST_USER_ID,
        route_id=route.id,
        email_to="wrongly-populated@example.com",
        email_subject="Application",
        email_body="Hello",
    )
    await approve_package(db_session, app.id, pkg.id, TEST_USER_ID)

    with pytest.raises(PackageError, match="Only EMAIL-route"):
        await send_package_email(db_session, app.id, pkg.id, TEST_USER_ID)


@pytest.mark.asyncio
async def test_qa_blocked_package_cannot_be_approved(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    pkg = await create_or_update_package(db_session, app.id, TEST_USER_ID, email_to="a@b.com")
    pkg.qa_verdict = QAVerdict.BLOCKED
    await db_session.commit()
    with pytest.raises(PackageError, match="QA-BLOCKED"):
        await approve_package(db_session, app.id, pkg.id, TEST_USER_ID)


# ---------------- attachment validation ----------------


def test_validate_attachments_rejects_foreign_attachment():
    class FakePackage:
        attachment_keys = ["users/u/resumes/r.pdf", "users/other/newer.pdf"]
        resume_id = "res1"

    with pytest.raises(PackageError, match="not part of the approved package"):
        validate_attachments(FakePackage(), {"users/u/resumes/r.pdf"}, set())


def test_validate_attachments_rejects_missing_resume():
    class FakePackage:
        attachment_keys = ["users/u/cover/cl.pdf"]
        resume_id = "res1"

    with pytest.raises(PackageError, match="resume version is not attached"):
        validate_attachments(FakePackage(), {"users/u/resumes/r.pdf"}, {"users/u/cover/cl.pdf"})


# ---------------- email send flow (Log provider = mocked transport) ----------------


@pytest.mark.asyncio
async def test_send_requires_approval(db_session):
    job = await _make_job(db_session)
    route = await _make_email_route(db_session, job)
    app = await _make_application(db_session, job)
    resume = await _make_resume(db_session)
    pkg = await create_or_update_package(
        db_session, app.id, TEST_USER_ID,
        resume_id=resume.id,
        email_to="jobs@techcorp.com",
        email_subject="Application",
        email_body="Hello",
        attachment_keys=["users/u/resumes/r.pdf"],
        route_id=route.id,
    )
    with pytest.raises(PackageError, match="No valid approval"):
        await send_package_email(db_session, app.id, pkg.id, TEST_USER_ID)


@pytest.mark.asyncio
async def test_send_success_records_sent_state(db_session):
    job = await _make_job(db_session)
    route = await _make_email_route(db_session, job)
    app = await _make_application(db_session, job)
    resume = await _make_resume(db_session)
    pkg = await create_or_update_package(
        db_session, app.id, TEST_USER_ID,
        resume_id=resume.id,
        email_to="jobs@techcorp.com",
        email_subject="Application",
        email_body="Hello",
        attachment_keys=["users/u/resumes/r.pdf"],
        route_id=route.id,
    )
    await approve_package(db_session, app.id, pkg.id, TEST_USER_ID)
    result = await send_package_email(db_session, app.id, pkg.id, TEST_USER_ID)
    assert result["state"] == "sent"
    assert result["message_id"]
    await db_session.refresh(pkg)
    assert pkg.send_state == EmailSendState.SENT
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.APPLIED

    # Single-use: second send is rejected
    from app.services.package_send import PackageError as PE

    with pytest.raises(PE, match="already been sent"):
        await send_package_email(db_session, app.id, pkg.id, TEST_USER_ID)


@pytest.mark.asyncio
async def test_stale_approval_cannot_send_newer_package(db_session):
    job = await _make_job(db_session)
    route = await _make_email_route(db_session, job)
    app = await _make_application(db_session, job)
    resume = await _make_resume(db_session)
    pkg1 = await create_or_update_package(
        db_session, app.id, TEST_USER_ID,
        resume_id=resume.id,
        email_to="jobs@techcorp.com",
        email_subject="Application",
        email_body="Hello",
        attachment_keys=["users/u/resumes/r.pdf"],
        route_id=route.id,
    )
    await approve_package(db_session, app.id, pkg1.id, TEST_USER_ID)

    # A component changes → new package version (approval bound to v1 hash).
    pkg2 = await create_or_update_package(
        db_session, app.id, TEST_USER_ID,
        email_subject="Application v2",
    )
    assert pkg2.version == 2

    # pkg1 is no longer current → cannot be sent
    with pytest.raises(PackageError, match="current package"):
        await send_package_email(db_session, app.id, pkg1.id, TEST_USER_ID)
    # pkg2 has no approval bound to ITS hash → cannot be sent
    with pytest.raises(PackageError, match="No valid approval"):
        await send_package_email(db_session, app.id, pkg2.id, TEST_USER_ID)


@pytest.mark.asyncio
async def test_stale_package_cannot_be_approved(db_session):
    job = await _make_job(db_session)
    app = await _make_application(db_session, job)
    pkg1 = await create_or_update_package(
        db_session, app.id, TEST_USER_ID, cover_letter_text="version one"
    )
    pkg2 = await create_or_update_package(
        db_session, app.id, TEST_USER_ID, cover_letter_text="version two"
    )
    assert pkg2.is_current

    with pytest.raises(PackageError, match="current package"):
        await approve_package(db_session, app.id, pkg1.id, TEST_USER_ID)
