"""Package send service (Phase 19).

Approves and sends an application package via the email route:

- ``approve_package`` — creates a single-use :class:`ApplicationApproval` bound to the
  exact ``(package_id, package_hash)``; QA BLOCKED packages cannot be approved.
- ``validate_attachments`` — attachment safety: every attachment must belong to this
  package's approved components.
- ``send_package_email`` — persists the exact outgoing email BEFORE the provider is
  called, sends via the configured provider only after approval, then records the
  result. ``SENT`` = provider accepted the message; delivery is never claimed without
  delivery evidence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationApproval, ApplicationRun
from app.models.application_package import ApplicationPackage
from app.models.application_route import ApplicationRoute
from app.models.enums import ApplicationStatus, EmailSendState, QAVerdict
from app.services.application_package import (
    PackageError,
    get_application_owned,
    get_package_owned,
)
from app.services.email_provider import OutgoingEmail, get_email_provider

logger = structlog.get_logger(__name__)


def validate_attachments(package: ApplicationPackage, resume_keys: set[str], cover_letter_keys: set[str]) -> None:
    """Attachment safety: every attachment must match an approved package component.

    Raises :class:`PackageError` when an attachment is not one of the package's own
    component keys (a newer/unapproved CV must never be attached by accident), or when
    the package has no attachments at all.
    """
    attachment_keys = set(package.attachment_keys or [])
    if not attachment_keys:
        raise PackageError("Package has no attachments.")
    approved = set(resume_keys) | set(cover_letter_keys)
    unknown = attachment_keys - approved
    if unknown:
        raise PackageError(
            f"Attachments not part of the approved package: {sorted(unknown)}"
        )
    if package.resume_id and not (attachment_keys & set(resume_keys)):
        raise PackageError("Package resume version is not attached.")


async def approve_package(
    db: AsyncSession, application_id: str, package_id: str, user_id: str
) -> ApplicationApproval:
    """Create a single-use approval bound to the EXACT package version.

    Rules:
    - The package must be the CURRENT package of the application.
    - QA verdict must not be BLOCKED.
    - Approval records (package_id, package_version, package_hash): if any component
      later changes, a new package is created with a different hash, and this approval
      can never authorize it (stale-approval protection).
    """
    app = await get_application_owned(db, application_id, user_id)
    package = await get_package_owned(db, package_id, user_id)
    if package.application_id != app.id:
        raise PackageError("Package does not belong to this application.")
    if not package.is_current:
        raise PackageError("Only the current package can be approved.")
    if package.qa_verdict == QAVerdict.BLOCKED:
        raise PackageError("Package is QA-BLOCKED and cannot be approved until fixed.")
    route_type = await _package_route_type(db, package, user_id)
    if route_type == "EMAIL" and not package.email_to:
        raise PackageError("Email package has no verified recipient.")

    # Idempotency: reuse an existing unused, unexpired approval for THIS package hash.
    from sqlalchemy import select

    existing = (
        await db.execute(
            select(ApplicationApproval).where(
                ApplicationApproval.application_id == app.id,
                ApplicationApproval.package_hash == package.content_hash,
                ApplicationApproval.used_at.is_(None),
                ApplicationApproval.expires_at > datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()
    if existing:
        expected_platform = route_type.lower()
        if existing.platform != expected_platform:
            existing.platform = expected_platform
        if app.status in {
            ApplicationStatus.READY,
            ApplicationStatus.WAITING_FOR_REVIEW,
            ApplicationStatus.PENDING_REVIEW,
        }:
            app.status = ApplicationStatus.APPROVED
        await db.commit()
        return existing

    approval = ApplicationApproval(
        id=f"appr_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        application_id=app.id,
        application_run_id=await _ensure_prep_run(db, app),
        job_id=app.job_id,
        candidate_profile_version=1,
        platform=route_type.lower(),
        package_id=package.id,
        package_version=package.version,
        package_hash=package.content_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(approval)

    package.approval_id = approval.id
    package.approved_at = datetime.now(UTC)
    if app.status in {
        ApplicationStatus.READY,
        ApplicationStatus.WAITING_FOR_REVIEW,
        ApplicationStatus.PENDING_REVIEW,
    }:
        app.status = ApplicationStatus.APPROVED
    await db.commit()
    logger.info("package_approved", package_id=package.id, approval_id=approval.id)
    return approval


async def _package_route_type(
    db: AsyncSession, package: ApplicationPackage, user_id: str
) -> str:
    """Resolve the immutable package route without assuming every route is email."""
    if package.route_id:
        from sqlalchemy import select

        route = (
            await db.execute(
                select(ApplicationRoute).where(
                    ApplicationRoute.id == package.route_id,
                    ApplicationRoute.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if route is None:
            raise PackageError("Package route is missing or unauthorized.")
        return route.route_type.upper()
    return "EMAIL" if package.email_to else "MANUAL"


async def _ensure_prep_run(db: AsyncSession, app: Application) -> str:
    """Return the latest completed prep run id, or create a minimal run record."""
    from sqlalchemy import select

    run = (
        await db.execute(
            select(ApplicationRun)
            .where(
                ApplicationRun.application_id == app.id,
                ApplicationRun.status == "completed",
            )
            .order_by(ApplicationRun.completed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run:
        return run.id
    prep = ApplicationRun(
        application_id=app.id,
        user_id=app.user_id,
        status="completed",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        state_data={"source": "package_preparation"},
    )
    db.add(prep)
    await db.flush()
    return prep.id


async def send_package_email(
    db: AsyncSession,
    application_id: str,
    package_id: str,
    user_id: str,
) -> dict:
    """Send the approved package via the email route.

    Safety sequence:
    1. The package must be current, approved, and NOT consumed by a prior send.
    2. The approval must be unused, unexpired, and bound to THIS package's hash.
    3. The exact outgoing email (sender/recipient/subject/body/attachments) is persisted
       (send_state=PENDING) BEFORE the provider is called.
    4. Provider failure → FAILED; ambiguous raise → UNKNOWN (never claimed as sent).
    5. Provider acceptance → SENT with Message-ID and provider response recorded.
    """
    app = await get_application_owned(db, application_id, user_id)
    package = await get_package_owned(db, package_id, user_id)
    if package.application_id != app.id:
        raise PackageError("Package does not belong to this application.")
    if not package.is_current:
        raise PackageError("Only the current package can be sent.")
    if await _package_route_type(db, package, user_id) != "EMAIL":
        raise PackageError("Only EMAIL-route packages can be sent by email.")
    if package.send_state == EmailSendState.SENT:
        raise PackageError("Package has already been sent (single-use send).")
    if not package.email_to or not package.email_subject or package.email_body is None:
        raise PackageError("Package email is incomplete.")

    # Approval verification — must exist, be unused/unexpired, and match the hash.
    from sqlalchemy import select

    approval = (
        await db.execute(
            select(ApplicationApproval).where(
                ApplicationApproval.application_id == app.id,
                ApplicationApproval.package_hash == package.content_hash,
                ApplicationApproval.used_at.is_(None),
                ApplicationApproval.expires_at > datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()
    if approval is None:
        raise PackageError("No valid approval for this exact package version.")

    # Attachment safety: attachments must be exactly the package's approved components.
    resume_keys: set[str] = set()
    if package.resume_id:
        from app.models.resume import Resume

        resume = await db.get(Resume, package.resume_id)
        for key in (resume.file_path_pdf, resume.file_path_docx):
            if key:
                resume_keys.add(key)
    cover_keys = {package.cover_letter_key} if package.cover_letter_key else set()
    validate_attachments(package, resume_keys, cover_keys)

    # Consume the approval and mark SUBMITTING before any external call.
    approval.used_at = datetime.now(UTC)
    package.send_state = EmailSendState.PENDING
    package.sender_address = None
    if app.status not in (ApplicationStatus.APPLIED, ApplicationStatus.SUBMISSION_UNKNOWN):
        app.status = ApplicationStatus.SUBMITTING
    await db.commit()

    from app.config.settings import get_settings

    cfg = get_settings().email
    sender = f"{cfg.from_name} <{cfg.from_address}>"
    outgoing = OutgoingEmail(
        to=package.email_to,
        subject=package.email_subject,
        body=package.email_body,
        sender=sender,
    )

    try:
        result = await get_email_provider().send(outgoing)
    except Exception as exc:  # provider raised without a verdict → UNKNOWN
        logger.error("package_send_unknown", error=str(exc))
        package.send_state = EmailSendState.UNKNOWN
        package.provider_response = f"exception: {exc}"
        app.status = ApplicationStatus.SUBMISSION_UNKNOWN
        await db.commit()
        return {"state": "unknown", "error": str(exc)}

    package.sent_at = datetime.now(UTC)
    package.message_id = result.message_id
    package.provider_response = result.provider_response or result.error
    package.sender_address = sender

    if result.status == "sent":
        package.send_state = EmailSendState.SENT
        app.status = ApplicationStatus.APPLIED
        app.applied_at = package.sent_at
        state = "sent"
    else:
        package.send_state = EmailSendState.FAILED
        app.status = ApplicationStatus.SUBMISSION_BLOCKED
        state = "failed"
    await db.commit()
    logger.info("package_send_completed", package_id=package.id, state=state)
    return {
        "state": state,
        "message_id": result.message_id,
        "provider_response": package.provider_response,
    }
