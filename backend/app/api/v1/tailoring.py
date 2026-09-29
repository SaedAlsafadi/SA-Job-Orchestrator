import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.llm.factory import build_llm_router_for_user
from app.models.enums import ReviewerStatus
from app.models.tailoring import CVTailoringSession
from app.models.user import User
from app.schemas.tailoring import (
    CVTailoringDecisionsRequest,
    CVTailoringReviseRequest,
    CVTailoringSessionSchema,
    CVTailoringStartRequest,
)
from app.services.tailoring import (
    get_or_create_revision_session,
    start_tailoring_session,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/tailoring", tags=["tailoring"])


@router.get("/resume/{resume_id}", response_model=CVTailoringSessionSchema)
async def api_get_session_for_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Resolve the existing workbench session that produced a tailored resume."""
    result = await db.execute(
        select(CVTailoringSession)
        .where(
            CVTailoringSession.final_resume_id == resume_id,
            CVTailoringSession.user_id == user.id,
        )
        .order_by(CVTailoringSession.updated_at.desc())
    )
    session = result.scalars().first()
    if session is None:
        raise HTTPException(status_code=404, detail="Tailoring session not found")
    await db.refresh(session, ["changes"])
    return session


@router.post("/resume/{resume_id}/revision", response_model=CVTailoringSessionSchema)
async def api_open_resume_revision(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Open a deterministic revision workbench, including for legacy résumés."""
    try:
        session = await get_or_create_revision_session(db, user.id, resume_id)
        await db.refresh(session, ["changes"])
        return session
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/start", response_model=CVTailoringSessionSchema)
async def api_start_tailoring(
    req: CVTailoringStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    accept_language: str = Header(default="en"),
):
    llm_router = await build_llm_router_for_user(db, user.id)
    try:
        session = await start_tailoring_session(
            db=db,
            user_id=user.id,
            job_id=req.job_id,
            base_resume_id=req.base_resume_id,
            router=llm_router,
        )
        # Load changes for response
        await db.refresh(session, ["changes"])
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}", response_model=CVTailoringSessionSchema)
async def api_get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CVTailoringSession).where(
            CVTailoringSession.id == session_id, CVTailoringSession.user_id == user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.refresh(session, ["changes"])
    return session


@router.post("/{session_id}/decisions", response_model=CVTailoringSessionSchema)
async def api_submit_decisions(
    session_id: str,
    req: CVTailoringDecisionsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Fetch session and verify ownership
    result = await db.execute(
        select(CVTailoringSession).where(
            CVTailoringSession.id == session_id, CVTailoringSession.user_id == user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.refresh(session, ["changes"])

    # Update decisions
    for change in session.changes:
        if change.change_id in req.decisions:
            new_status = req.decisions[change.change_id]
            # Rule: Cannot ACCEPT a BLOCKED change
            if (
                new_status == ReviewerStatus.ACCEPTED
                and change.review_severity == "blocked"
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot accept blocked change: {change.change_id}",
                )
            change.user_decision = new_status

    await db.commit()
    await db.refresh(session, ["changes"])
    return session


from app.schemas.resume import ResumeResponse
from app.services.tailoring import finalize_session, regenerate_session, revise_change


@router.post("/{session_id}/finalize", response_model=ResumeResponse)
async def api_finalize_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        new_resume = await finalize_session(db, user.id, session_id)
        return ResumeResponse.model_validate(new_resume)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/regenerate", response_model=CVTailoringSessionSchema)
async def api_regenerate_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    llm_router = await build_llm_router_for_user(db, user.id)
    try:
        new_session = await regenerate_session(db, user.id, session_id, llm_router)
        await db.refresh(new_session, ["changes"])
        return new_session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/revise")
async def api_revise_change(
    session_id: str,
    req: CVTailoringReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    accept_language: str = Header(default="en"),
):
    llm_router = await build_llm_router_for_user(db, user.id)
    try:
        new_change = await revise_change(
            db,
            user.id,
            session_id,
            req.change_id,
            req.instructions,
            llm_router,
            accept_language.split(",")[0].split("-")[0],
        )
        return new_change
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
