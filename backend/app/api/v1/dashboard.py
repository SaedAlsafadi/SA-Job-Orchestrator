"""Dashboard-only personalization endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_tenant_db
from app.models.dashboard_dismissal import DashboardDismissal
from app.schemas.dashboard import (
    DashboardDismissalCreate,
    DashboardDismissalList,
    DashboardDismissalResponse,
)

router = APIRouter()


@router.get("/dismissals", response_model=DashboardDismissalList)
async def list_dismissals(
    db: AsyncSession = Depends(get_tenant_db),
) -> DashboardDismissalList:
    rows = (await db.execute(select(DashboardDismissal))).scalars().all()
    return DashboardDismissalList(items=list(rows))


@router.post("/dismissals", response_model=DashboardDismissalResponse, status_code=201)
async def dismiss_item(
    payload: DashboardDismissalCreate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> DashboardDismissal:
    existing = (
        await db.execute(
            select(DashboardDismissal).where(
                DashboardDismissal.entity_type == payload.entity_type,
                DashboardDismissal.entity_id == payload.entity_id,
                DashboardDismissal.fingerprint == payload.fingerprint,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    row = DashboardDismissal(
        user_id=user.id, **payload.model_dump(), dismissed_at=datetime.now(UTC)
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/dismissals", status_code=204)
async def clear_dismissals(
    entity_type: str = Query(pattern="^(application|activity)$"),
    db: AsyncSession = Depends(get_tenant_db),
) -> Response:
    await db.execute(
        delete(DashboardDismissal).where(DashboardDismissal.entity_type == entity_type)
    )
    await db.commit()
    return Response(status_code=204)
