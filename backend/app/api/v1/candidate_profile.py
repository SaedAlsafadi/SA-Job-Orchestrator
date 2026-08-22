import uuid
import tempfile
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser, get_tenant_db
from app.models.candidate_profile import CandidateProfile, CandidateProfileVersion
from app.schemas.candidate_profile import CandidateProfileSchema, CandidateProfileResponse, CandidateProfileDraft
from app.core.documents.parser import DocumentParser
from app.core.llm.client import LLMClient

router = APIRouter()

@router.get("", response_model=CandidateProfileResponse)
async def get_profile(
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db)
) -> CandidateProfileResponse:
    profile = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    if not profile:
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
        languages=getattr(profile, 'languages', []),
        preferences=profile.preferences
    )

@router.put("", response_model=CandidateProfileResponse)
@router.post("/verify", response_model=CandidateProfileResponse)
async def update_profile(
    data: CandidateProfileSchema,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db)
) -> CandidateProfileResponse:
    profile = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    
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
            languages=data.languages,
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
        profile.languages = data.languages
        profile.preferences = data.preferences.model_dump()
        
    await db.commit()
    await db.refresh(profile)

    # Save to version history
    version_record = CandidateProfileVersion(
        profile_id=profile.id,
        user_id=user.id,
        version=profile.version,
        source="manual",
        profile_data=data.model_dump()
    )
    db.add(version_record)
    await db.commit()
    
    return CandidateProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        version=profile.version,
        **data.model_dump()
    )

@router.post("/import-resume", response_model=CandidateProfileDraft)
async def import_resume(
    user: CurrentUser,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db)
):
    import shutil
    
    # Save uploaded file to temp file for parser
    ext = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = Path(temp_file.name)
        
    try:
        # Parse document
        parser = DocumentParser()
        parsed_doc = await parser.parse(temp_path)
        
        # LLM Extraction
        llm = LLMClient()
        system_prompt = """
        You are an expert HR data extractor. Extract the candidate's professional profile from the provided resume text into a highly structured draft format.
        
        CRITICAL RULES:
        1. NEVER guess or infer information (like dates, nationality, visa status, or unsupported skills).
        2. Unknown values must be left null.
        3. Assign a confidence score (0.0 to 1.0) to every extracted value.
        4. "source" must be "resume" for every value.
        5. For multi-item fields (like skills, languages), extract each entry individually.
        """
        
        draft_response = await llm.complete_with_structured_output(
            prompt=f"Resume Text:\\n{parsed_doc.raw_text}",
            output_schema=CandidateProfileDraft,
            system_prompt=system_prompt
        )
        
        return draft_response
        
    finally:
        if temp_path.exists():
            os.remove(temp_path)




