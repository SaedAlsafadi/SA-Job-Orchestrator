"""Application package API (Phase 19).

Endpoints for the immutable application-package review flow:

- ``POST /applications/{app_id}/package``            — create/refresh the package
- ``GET  /applications/{app_id}/package``            — current package
- ``GET  /applications/{app_id}/readiness``         — "what remains before I can apply?"
- ``POST /applications/{app_id}/package/cover-letter`` — LLM cover letter (DeepSeek)
- ``POST /applications/{app_id}/package/email``      — LLM application email (DeepSeek)
- ``POST /applications/{app_id}/package/answers``    — LLM grounded answers (DeepSeek)
- ``POST /applications/{app_id}/package/qa``         — full-package QA (DeepSeek)
- ``POST /applications/{app_id}/package/approve``    — version-locked approval
- ``POST /applications/{app_id}/package/send``       — email-route send (approval required)

All routes are tenant-scoped; AI tasks run through the per-user LLMTaskRouter.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_tenant_db
from app.core.llm.factory import build_llm_router_for_user
from app.models.application_route import ApplicationRoute
from app.schemas.package import (
    AnswersGenRequest,
    CoverLetterGenRequest,
    EmailGenRequest,
    PackageCreate,
    PackageResponse,
    ReadinessResponse,
    SendResultResponse,
)
from app.services import application_package as package_service
from app.services import package_generation, package_send

logger = structlog.get_logger(__name__)
router = APIRouter()


def _package_to_response(package) -> PackageResponse:
    return PackageResponse.model_validate(package)


@router.post(
    "/applications/{app_id}/package",
    response_model=PackageResponse,
    summary="Create or refresh the application package (new immutable version on change)",
)
async def create_package(
    app_id: str,
    data: PackageCreate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> PackageResponse:
    try:
        package = await package_service.create_or_update_package(
            db, app_id, user.id,
            route_id=data.route_id,
            resume_id=data.resume_id,
            cover_letter_text=data.cover_letter_text,
            email_to=data.email_to,
            email_subject=data.email_subject,
            email_body=data.email_body,
            answers=data.answers,
            language=data.language,
        )
    except package_service.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _package_to_response(package)


@router.get(
    "/applications/{app_id}/package",
    response_model=PackageResponse | None,
    summary="Get the current application package",
)
async def get_package(
    app_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> PackageResponse | None:
    package = await package_service.get_current_package(db, app_id, user.id)
    return _package_to_response(package) if package else None


@router.get(
    "/applications/{app_id}/readiness",
    response_model=ReadinessResponse,
    summary="What remains before I can apply?",
)
async def get_readiness(
    app_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> ReadinessResponse:
    package = await package_service.get_current_package(db, app_id, user.id)
    if package is None:
        raise HTTPException(status_code=404, detail="No package created for this application yet.")
    readiness = await package_service.build_readiness(db, package)
    return ReadinessResponse(**readiness)


@router.post(
    "/applications/{app_id}/package/cover-letter",
    response_model=PackageResponse,
    summary="Generate the package cover letter (LLMTask.COVER_LETTER)",
)
async def gen_cover_letter(
    app_id: str,
    data: CoverLetterGenRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> PackageResponse:
    llm_router = await build_llm_router_for_user(db, user.id)
    current = await package_service.get_current_package(db, app_id, user.id)
    try:
        generated = await package_generation.generate_package_cover_letter(
            db, app_id, user.id, llm_router,
            match_summary=data.match_summary,
            language=data.language,
        )
        package = await package_service.create_or_update_package(
            db, app_id, user.id,
            cover_letter_text=generated.body,
            language=data.language,
        )
    except package_service.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _package_to_response(package)


@router.post(
    "/applications/{app_id}/package/email",
    response_model=PackageResponse,
    summary="Generate the application email (LLMTask.APPLICATION_EMAIL)",
)
async def gen_email(
    app_id: str,
    data: EmailGenRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> PackageResponse:
    llm_router = await build_llm_router_for_user(db, user.id)
    try:
        current = await package_service.get_current_package(db, app_id, user.id)
        route_email = None
        if current and current.route_id:
            route = await db.get(ApplicationRoute, current.route_id)
            route_email = route.email if route else None
        generated = await package_generation.generate_package_email(
            db, app_id, user.id, llm_router,
            route_email=route_email,
            cover_letter_text=current.cover_letter_text if current else None,
            language=data.language,
        )
        package = await package_service.create_or_update_package(
            db, app_id, user.id,
            email_to=generated.recipient,
            email_subject=generated.subject,
            email_body=generated.body,
            language=data.language,
        )
    except package_service.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _package_to_response(package)


@router.post(
    "/applications/{app_id}/package/answers",
    response_model=PackageResponse,
    summary="Generate grounded answers (LLMTask.APPLICATION_ANSWERS)",
)
async def gen_answers(
    app_id: str,
    data: AnswersGenRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> PackageResponse:
    llm_router = await build_llm_router_for_user(db, user.id)
    try:
        generated = await package_generation.generate_package_answers(
            db, app_id, user.id, llm_router,
            questions=data.questions,
            language=data.language,
        )
        answers = [a.model_dump() for a in generated.answers]
        package = await package_service.create_or_update_package(
            db, app_id, user.id, answers=answers, language=data.language,
        )
    except package_service.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _package_to_response(package)


@router.post(
    "/applications/{app_id}/package/qa",
    response_model=PackageResponse,
    summary="Run full-package QA (LLMTask.APPLICATION_QA)",
)
async def run_qa(
    app_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> PackageResponse:
    package = await package_service.get_current_package(db, app_id, user.id)
    if package is None:
        raise HTTPException(status_code=404, detail="No package created for this application yet.")
    llm_router = await build_llm_router_for_user(db, user.id)
    try:
        await package_generation.run_package_qa(db, package, llm_router)
    except package_service.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.refresh(package)
    return _package_to_response(package)


@router.post(
    "/applications/{app_id}/package/approve",
    response_model=PackageResponse,
    summary="Approve this exact package version (single-use, version-locked)",
)
async def approve(
    app_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> PackageResponse:
    package = await package_service.get_current_package(db, app_id, user.id)
    if package is None:
        raise HTTPException(status_code=404, detail="No package created for this application yet.")
    try:
        await package_send.approve_package(db, app_id, package.id, user.id)
    except package_send.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.refresh(package)
    return _package_to_response(package)


@router.post(
    "/applications/{app_id}/package/send",
    response_model=SendResultResponse,
    summary="Send the approved package via the email route (single-use)",
)
async def send(
    app_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
) -> SendResultResponse:
    package = await package_service.get_current_package(db, app_id, user.id)
    if package is None:
        raise HTTPException(status_code=404, detail="No package created for this application yet.")
    try:
        result = await package_send.send_package_email(db, app_id, package.id, user.id)
    except package_send.PackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SendResultResponse(**result)
