"""Pydantic schemas for the Candidate Profile."""

from __future__ import annotations

import uuid
from typing import Any
from pydantic import BaseModel, Field

def generate_evidence_id(prefix: str) -> str:
    """Generate a stable short ID for evidence tracking."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

class Identity(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""

class Location(BaseModel):
    country: str = ""
    city: str = ""
    preferred_locations: list[str] = Field(default_factory=list)
    willing_to_relocate: bool = False
    remote_preference: str = "hybrid" # remote, hybrid, onsite

class Employment(BaseModel):
    current_title: str = ""
    years_of_experience: int = 0
    notice_period: str = ""

class WorkAuthorization(BaseModel):
    nationality: str = ""
    residency_country: str = ""
    work_authorization_status: str = ""
    iqama_transferable: bool = False

class EducationEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("edu"))
    degree: str = ""
    institution: str = ""
    field_of_study: str = ""
    graduation_year: str = ""

class ExperienceEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("exp"))
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

class SkillEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("skill"))
    name: str = ""
    proficiency: str = "intermediate"
    years: int = 0
    evidence: str = ""

class ProjectEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("proj"))
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    url: str = ""

class CertificationEntry(BaseModel):
    evidence_id: str = Field(default_factory=lambda: generate_evidence_id("cert"))
    name: str = ""
    issuer: str = ""
    date: str = ""

class Preferences(BaseModel):
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
    preferences: Preferences = Field(default_factory=Preferences)

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
