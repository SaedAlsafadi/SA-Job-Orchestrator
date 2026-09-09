"""Application-package service (Phase 19).

Creates and manages immutable, version-locked :class:`ApplicationPackage` records and
computes the concise application-readiness summary ("What remains before I can apply?").

Version locking: every component change creates a NEW package row (``version + 1``) with
a fresh ``content_hash``; the previous row is marked ``is_current = False``. Approvals
bind to ``(package_id, package_hash)``, so a stale approval can never authorize a newer
package.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.application_package import ApplicationPackage
from app.models.application_route import ApplicationRoute
from app.models.enums import PostingQualitySignal, QAVerdict
from app.models.job import Job
from app.models.resume import Resume
from app.services.posting_quality import assess_posting_quality
from app.services.work_authorization import detect_work_requirements

logger = structlog.get_logger(__name__)


class PackageError(ValueError):
    """Raised when a package operation is invalid (maps to HTTP 400)."""


def compute_content_hash(
    *,
    application_id: str,
    route_id: str | None,
    resume_id: str | None,
    cover_letter_text: str | None,
    email_to: str | None,
    email_subject: str | None,
    email_body: str | None,
    attachment_keys: list | None,
    answers: list | None,
    language: str,
) -> str:
    """SHA-256 fingerprint over every component reference — the version-lock key."""
    payload = json.dumps(
        {
            "application_id": application_id,
            "route_id": route_id,
            "resume_id": resume_id,
            "cover_letter": (cover_letter_text or "").strip(),
            "email_to": (email_to or "").strip().lower(),
            "email_subject": (email_subject or "").strip(),
            "email_body": (email_body or "").strip(),
            "attachment_keys": sorted(attachment_keys or []),
            "answers": answers or [],
            "language": language,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_application_owned(
    db: AsyncSession, application_id: str, user_id: str
) -> Application:
    """Load an application owned by the user (tenant + explicit ownership check)."""
    app = (
        await db.execute(
            select(Application)
            .options(selectinload(Application.job))
            .where(Application.id == application_id, Application.user_id == user_id)
        )
    ).scalar_one_or_none()
    if app is None:
        raise PackageError("Application not found or unauthorized.")
    return app


async def get_current_package(
    db: AsyncSession, application_id: str, user_id: str
) -> ApplicationPackage | None:
    """Return the current package for an application (ownership verified)."""
    await get_application_owned(db, application_id, user_id)
    return (
        await db.execute(
            select(ApplicationPackage)
            .where(
                ApplicationPackage.application_id == application_id,
                ApplicationPackage.is_current.is_(True),
            )
            .order_by(ApplicationPackage.version.desc())
        )
    ).scalars().first()


async def get_package_owned(
    db: AsyncSession, package_id: str, user_id: str
) -> ApplicationPackage:
    """Load a specific package owned by the user."""
    package = (
        await db.execute(
            select(ApplicationPackage).where(
                ApplicationPackage.id == package_id,
                ApplicationPackage.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if package is None:
        raise PackageError("Package not found or unauthorized.")
    return package


async def _next_version(db: AsyncSession, application_id: str) -> int:
    latest = (
        await db.execute(
            select(ApplicationPackage.version)
            .where(ApplicationPackage.application_id == application_id)
            .order_by(ApplicationPackage.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return (latest or 0) + 1


async def _mark_previous_not_current(db: AsyncSession, application_id: str) -> None:
    previous = (
        await db.execute(
            select(ApplicationPackage).where(
                ApplicationPackage.application_id == application_id,
                ApplicationPackage.is_current.is_(True),
            )
        )
    ).scalars().all()
    for pkg in previous:
        pkg.is_current = False


async def _default_route_id(db: AsyncSession, app: Application) -> str | None:
    route = (
        await db.execute(
            select(ApplicationRoute)
            .where(ApplicationRoute.job_id == app.job_id)
            .order_by(
                ApplicationRoute.is_preferred.desc(), ApplicationRoute.resolved_at.desc()
            )
        )
    ).scalars().first()
    return route.id if route else None


async def create_or_update_package(
    db: AsyncSession,
    application_id: str,
    user_id: str,
    *,
    route_id: str | None = None,
    resume_id: str | None = None,
    cover_letter_key: str | None = None,
    cover_letter_text: str | None = None,
    email_to: str | None = None,
    email_subject: str | None = None,
    email_body: str | None = None,
    attachment_keys: list | None = None,
    answers: list | None = None,
    language: str = "en",
) -> ApplicationPackage:
    """Create the package (or a new immutable version when a component changed).

    If the resulting component set hashes identically to the current package, the
    existing package is returned unchanged (idempotent).
    """
    app = await get_application_owned(db, application_id, user_id)
    current = await get_current_package(db, application_id, user_id)

    # Defaults from the application / current package when not explicitly provided.
    if route_id is None:
        route_id = current.route_id if current else await _default_route_id(db, app)
    if route_id:
        route = await db.get(ApplicationRoute, route_id)
        if route is None or route.user_id != user_id or route.job_id != app.job_id:
            raise PackageError("Application route not found or unauthorized.")
    if resume_id is None:
        resume_id = current.resume_id if current else app.resume_id

    # Resolve attachment storage keys on the server.  Resume list responses only
    # expose has_pdf/has_docx (never internal storage paths), and accepting paths
    # supplied by the browser would also weaken the attachment ownership boundary.
    # PackageCreate therefore does not expose cover_letter_key/attachment_keys;
    # those arguments are reserved for trusted service-to-service callers.
    resume = None
    if resume_id:
        resume = await db.get(Resume, resume_id)
        if resume is None or resume.user_id != user_id:
            raise PackageError("Resume not found or unauthorized.")
    if cover_letter_text is None and current:
        cover_letter_key = cover_letter_key or current.cover_letter_key
        cover_letter_text = current.cover_letter_text
    if email_to is None and current:
        email_to = current.email_to
    if email_subject is None and current:
        email_subject = current.email_subject
    if email_body is None and current:
        email_body = current.email_body
    if attachment_keys is None:
        if current and resume_id == current.resume_id:
            attachment_keys = current.attachment_keys
        elif resume:
            attachment_keys = [
                key
                for key in (resume.file_path_pdf, resume.file_path_docx)
                if key
            ]
    if answers is None and current:
        answers = current.answers

    content_hash = compute_content_hash(
        application_id=application_id,
        route_id=route_id,
        resume_id=resume_id,
        cover_letter_text=cover_letter_text,
        email_to=email_to,
        email_subject=email_subject,
        email_body=email_body,
        attachment_keys=attachment_keys,
        answers=answers,
        language=language,
    )

    if current and current.content_hash == content_hash:
        return current  # nothing changed — same immutable package

    await _mark_previous_not_current(db, application_id)
    package = ApplicationPackage(
        id=f"pkg_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        application_id=application_id,
        job_id=app.job_id,
        route_id=route_id,
        resume_id=resume_id,
        cover_letter_key=cover_letter_key,
        cover_letter_text=cover_letter_text,
        email_to=email_to,
        email_subject=email_subject,
        email_body=email_body,
        attachment_keys=attachment_keys,
        answers=answers,
        language=language,
        version=await _next_version(db, application_id),
        content_hash=content_hash,
        is_current=True,
        # A new version invalidates any prior approval/QA/send state by construction:
        # the approval binds to the OLD package_id/hash and can never match this one.
    )
    db.add(package)
    await db.commit()
    await db.refresh(package)
    logger.info(
        "package_created",
        application_id=application_id,
        package_id=package.id,
        version=package.version,
    )
    return package


async def build_readiness(db: AsyncSession, package: ApplicationPackage) -> dict:
    """Concise readiness summary answering: "What remains before I can apply?"."""
    job = await db.get(Job, package.job_id)
    if job is None:  # pragma: no cover — FK guarantees existence
        raise PackageError("Package job not found.")

    quality = assess_posting_quality(job)
    work_auth = detect_work_requirements(f"{job.description or ''}\n{job.requirements or ''}")

    documents: list[dict] = []
    missing: list[str] = []
    warnings: list[str] = []

    # Resume (immutable version)
    resume = await db.get(Resume, package.resume_id) if package.resume_id else None
    if resume and (resume.file_path_pdf or resume.file_path_docx):
        documents.append({"name": "Tailored CV", "ok": True, "detail": "verified"})
    else:
        documents.append({"name": "Tailored CV", "ok": False, "detail": "missing"})
        missing.append("tailored CV")

    # Cover letter
    if package.cover_letter_text:
        documents.append({"name": "Cover Letter", "ok": True, "detail": "drafted"})
    else:
        documents.append({"name": "Cover Letter", "ok": False, "detail": "not generated"})
        missing.append("cover letter")

    # Application email (email route only)
    route_type = None
    if package.route_id:
        route = await db.get(ApplicationRoute, package.route_id)
        route_type = route.route_type if route else None
    if route_type == "EMAIL":
        if package.email_to and package.email_subject and package.email_body:
            documents.append({"name": "Application Email", "ok": True, "detail": "drafted"})
        else:
            documents.append({"name": "Application Email", "ok": False, "detail": "not drafted"})
            missing.append("application email")

    # QA verdict
    if package.qa_verdict == QAVerdict.BLOCKED:
        missing.append("QA blockers must be fixed")
    elif package.qa_verdict == QAVerdict.WARNING:
        warnings.append("QA raised warnings — review before approving")

    # Posting-quality + work-authorization signals (signals, not verdicts)
    if quality.signal == PostingQualitySignal.SUSPICIOUS:
        warnings.append("posting shows suspicious signals — verify before applying")
    elif quality.signal == PostingQualitySignal.NEEDS_REVIEW:
        warnings.append("posting quality needs review")
    if work_auth.status == "RESTRICTED":
        warnings.append("work-authorization restriction stated in posting")
    elif work_auth.status == "UNKNOWN":
        warnings.append("work-authorization requirements unknown")

    ready = not missing and package.qa_verdict != QAVerdict.BLOCKED
    return {
        "ready": ready,
        "missing": missing,
        "warnings": warnings,
        "documents": documents,
        "route": route_type,
        "posting_quality": quality.as_dict(),
        "work_authorization": work_auth.as_dict(),
        "package_version": package.version,
        "content_hash": package.content_hash,
        "approved": package.approval_id is not None,
        "send_state": package.send_state.value if package.send_state else None,
    }
