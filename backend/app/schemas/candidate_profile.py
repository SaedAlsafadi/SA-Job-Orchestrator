"""Pydantic schemas for the Candidate Profile."""

from __future__ import annotations

import uuid
from pydantic import BaseModel, Field, model_validator, field_validator

def generate_evidence_id(prefix: str) -> str:
    """Generate a stable short ID for evidence tracking."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

class FlexibleModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def flatten_dict_values(cls, data: Any) -> Any:
        if isinstance(data, dict):
            flattened = {}
            for k, v in data.items():
                if isinstance(v, dict) and "value" in v:
                    val = v.get("value")
                    flattened[k] = val if val is not None else ""
                else:
                    flattened[k] = v
            return flattened
        return data

class Identity(FlexibleModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    professional_summary: str = ""

class Location(FlexibleModel):
    country: str = ""
    city: str = ""
    preferred_locations: list[str] = Field(default_factory=list)
    willing_to_relocate: bool = False
    remote_preference: str = "hybrid" # remote, hybrid, onsite

class Employment(FlexibleModel):
    current_title: str = ""
    years_of_experience: int = 0
    notice_period: str = ""

class WorkAuthorization(FlexibleModel):
    nationality: str = ""
    residency_country: str = ""
    work_authorization_status: str = ""
    iqama_transferable: bool = False

class EducationEntry(FlexibleModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("edu"))
    degree: str = ""
    institution: str = ""
    field_of_study: str = ""
    graduation_year: str = ""

class ExperienceEntry(FlexibleModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("exp"))
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

class SkillEntry(FlexibleModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("skill"))
    name: str = ""
    proficiency: str = "intermediate"
    years: int = 0
    evidence: str = ""

    @model_validator(mode="before")
    @classmethod
    def parse_skill(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"name": data}
        if isinstance(data, dict):
            if "value" in data and "name" not in data:
                return {
                    "name": data.get("value") or "",
                    "evidence_id": data.get("evidence_id", generate_evidence_id("skill"))
                }
            flattened = {}
            for k, v in data.items():
                if isinstance(v, dict) and "value" in v:
                    val = v.get("value")
                    flattened[k] = val if val is not None else ""
                else:
                    flattened[k] = v
            return flattened
        return data

class ProjectEntry(FlexibleModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("proj"))
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    url: str = ""

class CertificationEntry(FlexibleModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("cert"))
    name: str = ""
    issuer: str = ""
    date: str = ""

class Preferences(FlexibleModel):
    target_roles: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    target_cities: list[str] = Field(default_factory=list)
    minimum_salary: int = 0
    salary_currency: str = "USD"
    employment_types: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)

class CandidateProfileSchema(BaseModel):
    """The master schema for validating a candidate profile."""
    identity: Identity = Field(default_factory=Identity)
    location: Location = Field(default_factory=Location)
    employment: Employment = Field(default_factory=Employment)
    work_authorization: WorkAuthorization = Field(default_factory=WorkAuthorization)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    skills: list[SkillEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)

    @field_validator("languages", mode="before")
    @classmethod
    def parse_languages(cls, v: Any) -> Any:
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, str):
                    if item.strip():
                        out.append(item.strip())
                elif isinstance(item, dict) and "value" in item:
                    val = item.get("value")
                    if val and str(val).strip():
                        out.append(str(val).strip())
            return out
        return v

    def get_all_evidence_ids(self) -> set[str]:
        """Collect all generated evidence IDs for anti-hallucination validation."""
        ids = set()
        for edu in self.education:
            ids.add(edu.evidence_id)
        for exp in self.experience:
            ids.add(exp.evidence_id)
        for skill in self.skills:
            ids.add(skill.evidence_id)
        for proj in self.projects:
            ids.add(proj.evidence_id)
        for cert in self.certifications:
            ids.add(cert.evidence_id)
        return ids

class CandidateProfileResponse(CandidateProfileSchema):
    """Response model includes database IDs."""
    id: str
    user_id: str
    version: int
from typing import Generic, TypeVar

T = TypeVar("T")

class DraftValue(BaseModel, Generic[T]):
    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = "resume"

class DraftIdentity(BaseModel):
    first_name: DraftValue[str] = Field(default_factory=DraftValue)
    last_name: DraftValue[str] = Field(default_factory=DraftValue)
    email: DraftValue[str] = Field(default_factory=DraftValue)
    phone: DraftValue[str] = Field(default_factory=DraftValue)
    linkedin: DraftValue[str] = Field(default_factory=DraftValue)
    github: DraftValue[str] = Field(default_factory=DraftValue)
    portfolio: DraftValue[str] = Field(default_factory=DraftValue)
    professional_summary: DraftValue[str] = Field(default_factory=DraftValue)

class DraftLocation(BaseModel):
    country: DraftValue[str] = Field(default_factory=DraftValue)
    city: DraftValue[str] = Field(default_factory=DraftValue)

class DraftEducationEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("edu"))
    degree: DraftValue[str] = Field(default_factory=DraftValue)
    institution: DraftValue[str] = Field(default_factory=DraftValue)
    field_of_study: DraftValue[str] = Field(default_factory=DraftValue)
    graduation_year: DraftValue[str] = Field(default_factory=DraftValue)

class DraftExperienceEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("exp"))
    company: DraftValue[str] = Field(default_factory=DraftValue)
    title: DraftValue[str] = Field(default_factory=DraftValue)
    start_date: DraftValue[str] = Field(default_factory=DraftValue)
    end_date: DraftValue[str] = Field(default_factory=DraftValue)
    description: DraftValue[str] = Field(default_factory=DraftValue)

class DraftProjectEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("proj"))
    name: DraftValue[str] = Field(default_factory=DraftValue)
    description: DraftValue[str] = Field(default_factory=DraftValue)
    url: DraftValue[str] = Field(default_factory=DraftValue)

class DraftCertificationEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("cert"))
    name: DraftValue[str] = Field(default_factory=DraftValue)
    issuer: DraftValue[str] = Field(default_factory=DraftValue)
    date: DraftValue[str] = Field(default_factory=DraftValue)

class CandidateProfileDraft(BaseModel):
    identity: DraftIdentity = Field(default_factory=DraftIdentity)
    location: DraftLocation = Field(default_factory=DraftLocation)
    education: list[DraftEducationEntry] = Field(default_factory=list)
    experience: list[DraftExperienceEntry] = Field(default_factory=list)
    skills: list[DraftValue[str]] = Field(default_factory=list)
    projects: list[DraftProjectEntry] = Field(default_factory=list)
    certifications: list[DraftCertificationEntry] = Field(default_factory=list)
    languages: list[DraftValue[str]] = Field(default_factory=list)

