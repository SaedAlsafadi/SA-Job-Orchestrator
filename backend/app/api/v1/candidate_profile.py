import uuid
import json
import tempfile
import os
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser, get_tenant_db
from app.models.candidate_profile import CandidateProfile, CandidateProfileVersion
from app.schemas.candidate_profile import (
    CandidateProfileSchema, CandidateProfileResponse, CandidateProfileDraft,
    DraftValue, DraftIdentity, DraftLocation,
    DraftEducationEntry, DraftExperienceEntry, DraftProjectEntry, DraftCertificationEntry,
    generate_evidence_id,
)
from app.core.documents.parser import DocumentParser
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter, LLMTask
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# --------------------------------------------------------------------------- #
# Simplified LLM extraction schema — flat strings, no DraftValue wrappers.
# Even a small free model can reliably produce this format.
# --------------------------------------------------------------------------- #

class _LLMIdentity(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    professional_summary: str | None = None

class _LLMLocation(BaseModel):
    country: str | None = None
    city: str | None = None

class _LLMEducation(BaseModel):
    degree: str | None = None
    institution: str | None = None
    field_of_study: str | None = None
    graduation_year: str | None = None

class _LLMExperience(BaseModel):
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None

class _LLMProject(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None

class _LLMCertification(BaseModel):
    name: str | None = None
    issuer: str | None = None
    date: str | None = None

class _LLMExtraction(BaseModel):
    """Simplified flat schema the LLM fills. We transform it into DraftValue after."""
    identity: _LLMIdentity = Field(default_factory=_LLMIdentity)
    location: _LLMLocation = Field(default_factory=_LLMLocation)
    education: list[_LLMEducation] = Field(default_factory=list)
    experience: list[_LLMExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[_LLMProject] = Field(default_factory=list)
    certifications: list[_LLMCertification] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


def _wrap(value: str | None, confidence: float = 0.95) -> DraftValue[str]:
    """Wrap a plain string into a DraftValue with confidence."""
    if value is None or value == "":
        return DraftValue()
    return DraftValue(value=value, confidence=confidence, source="resume")


def _llm_to_draft(llm: _LLMExtraction) -> CandidateProfileDraft:
    """Transform flat LLM output into a proper CandidateProfileDraft with DraftValue wrappers."""
    identity = DraftIdentity(
        first_name=_wrap(llm.identity.first_name),
        last_name=_wrap(llm.identity.last_name),
        email=_wrap(llm.identity.email, 0.99),
        phone=_wrap(llm.identity.phone, 0.99),
        linkedin=_wrap(llm.identity.linkedin, 0.99),
        github=_wrap(llm.identity.github, 0.99),
        portfolio=_wrap(llm.identity.portfolio, 0.90),
        professional_summary=_wrap(llm.identity.professional_summary, 0.85),
    )
    location = DraftLocation(
        country=_wrap(llm.location.country, 0.80),
        city=_wrap(llm.location.city, 0.80),
    )
    education = [
        DraftEducationEntry(
            evidence_id=generate_evidence_id("edu"),
            degree=_wrap(e.degree),
            institution=_wrap(e.institution),
            field_of_study=_wrap(e.field_of_study),
            graduation_year=_wrap(e.graduation_year),
        )
        for e in llm.education
    ]
    experience = [
        DraftExperienceEntry(
            evidence_id=generate_evidence_id("exp"),
            company=_wrap(e.company),
            title=_wrap(e.title),
            start_date=_wrap(e.start_date),
            end_date=_wrap(e.end_date),
            description=_wrap(e.description, 0.85),
        )
        for e in llm.experience
    ]
    skills = [_wrap(s) for s in llm.skills if s]
    projects = [
        DraftProjectEntry(
            evidence_id=generate_evidence_id("proj"),
            name=_wrap(p.name),
            description=_wrap(p.description, 0.85),
            url=_wrap(p.url, 0.99),
        )
        for p in llm.projects
    ]
    certifications = [
        DraftCertificationEntry(
            evidence_id=generate_evidence_id("cert"),
            name=_wrap(c.name),
            issuer=_wrap(c.issuer),
            date=_wrap(c.date),
        )
        for c in llm.certifications
    ]
    languages = [_wrap(lang) for lang in llm.languages if lang]

    return CandidateProfileDraft(
        identity=identity,
        location=location,
        education=education,
        experience=experience,
        skills=skills,
        projects=projects,
        certifications=certifications,
        languages=languages,
    )


def _fallback_from_parsed(parsed_doc) -> CandidateProfileDraft:
    """Build a minimal draft from DocumentParser metadata when LLM is unavailable."""
    draft = CandidateProfileDraft()

    contact = parsed_doc.contact_info
    if contact.get("email"):
        draft.identity.email = _wrap(contact["email"], 0.99)
    if contact.get("phone"):
        draft.identity.phone = _wrap(contact["phone"], 0.99)
    if contact.get("linkedin"):
        draft.identity.linkedin = _wrap(contact["linkedin"], 0.99)
    if contact.get("github"):
        draft.identity.github = _wrap(contact["github"], 0.99)

    # Put parsed text in professional summary so the user can manually split it
    draft.identity.professional_summary = DraftValue(
        value=parsed_doc.raw_text[:3000],
        confidence=1.0,
        source="resume_fallback",
    )

    # Turn parser-detected skills into draft skill values
    draft.skills = [_wrap(s, 0.70) for s in parsed_doc.skills[:30]]

    return draft


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

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
        
        # LLM Extraction — use simplified flat schema, then transform
        llm = LLMTaskRouter(LLMClient())
        system_prompt = """You are an expert resume parser. Read the resume text and extract ALL information into JSON.

You MUST populate every field that has data in the resume. Here is an example output:

{
  "identity": {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john@example.com",
    "phone": "+1 555 123 4567",
    "linkedin": "linkedin.com/in/johnsmith",
    "github": "github.com/johnsmith",
    "portfolio": null,
    "professional_summary": "Experienced software engineer with 5 years..."
  },
  "location": {"country": "Saudi Arabia", "city": "Riyadh"},
  "education": [
    {"degree": "BSc Computer Science", "institution": "MIT", "field_of_study": "Computer Science", "graduation_year": "2019"}
  ],
  "experience": [
    {"company": "TechCorp", "title": "Senior Engineer", "start_date": "2021", "end_date": "Present", "description": "Led backend development using Python/FastAPI. Designed microservices on AWS."}
  ],
  "skills": ["Python", "TypeScript", "FastAPI", "React", "AWS", "Docker"],
  "projects": [],
  "certifications": [],
  "languages": ["English", "Arabic"]
}

RULES:
- Extract the person's first_name and last_name from the top of the resume.
- The professional_summary should be a 2-3 sentence overview from the resume.
- List EVERY skill mentioned anywhere in the resume in the skills array.
- For experience: extract company, title, dates, and combine bullet points into the description.
- Set null for fields NOT found in the resume. Do NOT invent data."""
        
        try:
            llm_result = await llm.complete_with_structured_output(
                task=LLMTask.METADATA_EXTRACTION,
                prompt=f"Resume Text:\n{parsed_doc.raw_text}",
                output_schema=_LLMExtraction,
                system_prompt=system_prompt
            )
            # Transform flat LLM output → DraftValue-wrapped draft
            draft = _llm_to_draft(llm_result)

            # Supplement with parser-detected contact info the LLM may have missed
            contact = parsed_doc.contact_info
            if contact.get("email") and not draft.identity.email.value:
                draft.identity.email = _wrap(contact["email"], 0.99)
            if contact.get("phone") and not draft.identity.phone.value:
                draft.identity.phone = _wrap(contact["phone"], 0.99)
            if contact.get("linkedin") and not draft.identity.linkedin.value:
                draft.identity.linkedin = _wrap(contact["linkedin"], 0.99)
            if contact.get("github") and not draft.identity.github.value:
                draft.identity.github = _wrap(contact["github"], 0.99)

            # Supplement skills from parser if LLM missed them
            llm_skill_names = {(s.value or "").lower() for s in draft.skills}
            for parser_skill in parsed_doc.skills:
                if parser_skill.lower() not in llm_skill_names:
                    draft.skills.append(_wrap(parser_skill, 0.70))

            return draft

        except Exception as llm_exc:
            logger.error(f"LLM extraction failed, using deterministic fallback: {llm_exc}")
            return _fallback_from_parsed(parsed_doc)
            
    finally:
        if temp_path.exists():
            os.remove(temp_path)

