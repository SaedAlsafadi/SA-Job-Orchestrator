"""System-wide anomaly detection.

Beyond individual apply runs, the harness watches workflow/system health and records
``SystemIssue`` rows (surfaced on an admin/health view). Rule-based and global (not
tenant-scoped), so application counts bypass the tenant filter.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import ApplicationStatus
from app.models.harness import SystemIssue

logger = structlog.get_logger(__name__)

MIN_SAMPLE = 5
FAILED_RATE_THRESHOLD = 0.5
QUEUE_DEPTH_THRESHOLD = 100
_ARQ_QUEUE = "arq:queue"


def _issue(
    category: str, severity: str, signals: dict, diagnosis: str, now: datetime
) -> SystemIssue:
    return SystemIssue(
        category=category,
        severity=severity,
        signals=signals,
        diagnosis=diagnosis,
        detected_at=now,
        status="open",
    )


async def detect_anomalies(
    db: AsyncSession, *, redis: object | None = None, now: datetime | None = None
) -> list[SystemIssue]:
    """Inspect workflow health and persist any detected ``SystemIssue`` rows."""
    now = now or datetime.now(UTC)
    issues: list[SystemIssue] = []

    # 1. High recent application-failure rate (global; bypass the tenant filter).
    total = (
        await db.execute(
            select(func.count(Application.id)).execution_options(skip_tenant_filter=True)
        )
    ).scalar() or 0
    failed = (
        await db.execute(
            select(func.count(Application.id))
            .where(Application.status == ApplicationStatus.FAILED)
            .execution_options(skip_tenant_filter=True)
        )
    ).scalar() or 0
    if total >= MIN_SAMPLE and failed / total >= FAILED_RATE_THRESHOLD:
        issues.append(
            _issue(
                "apply_failure_rate",
                "critical",
                {"total": total, "failed": failed},
                f"{failed}/{total} applications are in FAILED state",
                now,
            )
        )

    # 2. Queue backlog.
    if redis is not None:
        try:
            depth = await redis.llen(_ARQ_QUEUE)
        except Exception:
            depth = 0
        if depth and depth > QUEUE_DEPTH_THRESHOLD:
            issues.append(
                _issue("queue_depth", "warning", {"depth": depth}, f"Queue backlog: {depth}", now)
            )

    for issue in issues:
        db.add(issue)
    if issues:
        await db.commit()
        for issue in issues:
            await db.refresh(issue)
        logger.info("anomaly.detected", count=len(issues))
    return issues
