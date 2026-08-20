"""Candidate Profile API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser, get_tenant_db
from app.models.candidate_profile import CandidateProfile
from app.schemas.candidate_profile import CandidateProfileSchema, CandidateProfileResponse

router = APIRouter()

@router.get("", response_model=CandidateProfileResponse)
async def get_profile(
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db)
) -> CandidateProfileResponse:
    profile = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    if not profile:
        # Return empty schema if none exists
        return CandidateProfileResponse(id="none", user_id=user.id, version=0)
        
    return CandidateProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        version=profile.version,
        identity=profile.identity,
        location=profile.location,
        employment=profile.employment,
        work_authorization=profile.work_authorization,
        education=profile.education,
        experience=profile.experience,
        skills=profile.skills,
        projects=profile.projects,
        certifications=profile.certifications,
        preferences=profile.preferences
    )

@router.post("", response_model=CandidateProfileResponse)
async def update_profile(
    data: CandidateProfileSchema,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db)
) -> CandidateProfileResponse:
    profile = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    
    # Validation happens automatically via Pydantic mapping
    
    if not profile:
        profile = CandidateProfile(
            user_id=user.id,
            version=1,
            identity=data.identity.model_dump(),
            location=data.location.model_dump(),
            employment=data.employment.model_dump(),
            work_authorization=data.work_authorization.model_dump(),
            education=[e.model_dump() for e in data.education],
            experience=[e.model_dump() for e in data.experience],
            skills=[s.model_dump() for s in data.skills],
            projects=[p.model_dump() for p in data.projects],
            certifications=[c.model_dump() for c in data.certifications],
            preferences=data.preferences.model_dump()
        )
        db.add(profile)
    else:
        profile.version += 1
        profile.identity = data.identity.model_dump()
        profile.location = data.location.model_dump()
        profile.employment = data.employment.model_dump()
        profile.work_authorization = data.work_authorization.model_dump()
        profile.education = [e.model_dump() for e in data.education]
        profile.experience = [e.model_dump() for e in data.experience]
        profile.skills = [s.model_dump() for s in data.skills]
        profile.projects = [p.model_dump() for p in data.projects]
        profile.certifications = [c.model_dump() for c in data.certifications]
        profile.preferences = data.preferences.model_dump()
        
    await db.commit()
    await db.refresh(profile)
    
    return CandidateProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        version=profile.version,
        **data.model_dump()
    )
