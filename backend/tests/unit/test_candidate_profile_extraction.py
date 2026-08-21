import pytest
from app.schemas.candidate_profile import CandidateProfileDraft, DraftValue, DraftIdentity, CandidateProfileSchema, generate_evidence_id
from app.models.candidate_profile import CandidateProfile, CandidateProfileVersion


def test_evidence_id_generation():
    eid = generate_evidence_id("test")
    assert eid.startswith("test-")
    assert len(eid) > 5

def test_draft_schema_instantiation():
    draft = CandidateProfileDraft(
        identity=DraftIdentity(
            first_name=DraftValue[str](value="John", confidence=0.95, source="resume"),
            last_name=DraftValue[str](value="Doe", confidence=0.99, source="resume")
        ),
        skills=[DraftValue[str](value="Python", confidence=0.98, source="resume")]
    )
    
    assert draft.identity.first_name.value == "John"
    assert draft.identity.first_name.confidence == 0.95
    assert draft.skills[0].value == "Python"
    
def test_unknown_fields_are_null():
    draft = CandidateProfileDraft()
    assert draft.identity.first_name.value is None
    assert draft.identity.email.value is None
    
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.candidate_profile import CandidateProfile, CandidateProfileVersion
from sqlalchemy import select

@pytest.mark.asyncio
async def test_update_profile_creates_version(
    client, current_user,
    db_session: AsyncSession,
    
    
):
    payload = {
        "identity": {
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com"
        },
        "location": {},
        "employment": {},
        "work_authorization": {},
        "education": [],
        "experience": [],
        "skills": [{"name": "Python", "proficiency": "expert", "years": 5}],
        "projects": [],
        "certifications": [],
        "languages": ["English"],
        "preferences": {}
    }
    
    
    
    # Verify POST /api/v1/candidate-profile/verify
    res = await client.post("/api/v1/candidate-profile/verify", json=payload, )
    assert res.status_code == 200, res.text
    
    data = res.json()
    assert data["version"] == 1
    assert data["identity"]["first_name"] == "Test"
    
    # Check DB for version
    versions = (await db_session.execute(select(CandidateProfileVersion).where(CandidateProfileVersion.user_id == current_user.id))).scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1
    
    # Update again
    payload["identity"]["first_name"] = "Updated"
    res2 = await client.post("/api/v1/candidate-profile/verify", json=payload, )
    assert res2.status_code == 200
    
    data2 = res2.json()
    assert data2["version"] == 2
    assert data2["identity"]["first_name"] == "Updated"
    
    # Check DB for version 2
    versions = (await db_session.execute(select(CandidateProfileVersion).where(CandidateProfileVersion.user_id == current_user.id))).scalars().all()
    assert len(versions) == 2
