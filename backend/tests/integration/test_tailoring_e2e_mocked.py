import pytest
import uuid
import json
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.enums import TailoringStatus, ChangeType, ReviewerStatus, ReviewSeverity
from app.models.resume import Resume
from app.models.job import Job
from app.models.tailoring import CVTailoringSession, CVTailoringChange
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.schemas.tailoring import CVTailorOutput, CVReviewOutput, ProposedChangeOutput, ReviewDecisionOutput
from app.services.tailoring import start_tailoring_session, finalize_session, revise_change, regenerate_session
from app.core.documents.generator import DocumentGenerator

@pytest.fixture
def mock_tailor_output():
    return CVTailorOutput(
        changes=[
            ProposedChangeOutput(
                target_type="inline",
                target_reference="skills[0]",
                section="skills",
                original_text="Python",
                proposed_text="Python/FastAPI",
                change_type=ChangeType.MODIFY,
                reason="Job explicitly requests FastAPI",
                linked_requirement_ids=["req1"],
                linked_evidence_ids=["ev1"]
            ),
            ProposedChangeOutput(
                target_type="inline",
                target_reference="experience[0].title",
                section="experience",
                original_text="Backend Dev",
                proposed_text="Senior Backend Dev",
                change_type=ChangeType.MODIFY,
                reason="Make candidate look more senior",
                linked_requirement_ids=["req2"],
                linked_evidence_ids=[]
            ),
            ProposedChangeOutput(
                target_type="inline",
                target_reference="skills[1]",
                section="skills",
                original_text="PHP",
                proposed_text=None,
                change_type=ChangeType.REMOVE,
                reason="Irrelevant to modern stack",
                linked_requirement_ids=[],
                linked_evidence_ids=[]
            )
        ]
    )

@pytest.fixture
def mock_review_output():
    return CVReviewOutput(
        reviews=[
            ReviewDecisionOutput(
                change_id="IGNORED_IN_MOCK_BECAUSE_MAPPED_LATER", # Mapped in test
                severity=ReviewSeverity.SAFE,
                reason="Accurate representation of skills"
            ),
            ReviewDecisionOutput(
                change_id="IGNORED_IN_MOCK_BECAUSE_MAPPED_LATER",
                severity=ReviewSeverity.BLOCKED,
                reason="Hallucinated seniority level without evidence"
            ),
            ReviewDecisionOutput(
                change_id="IGNORED_IN_MOCK_BECAUSE_MAPPED_LATER",
                severity=ReviewSeverity.WARNING,
                reason="Removing skills is safe but may omit keywords"
            )
        ]
    )

@pytest.mark.asyncio
async def test_full_tailoring_workflow(db_session: AsyncSession, current_user, mock_tailor_output, mock_review_output):
    # 1. Setup Data
    job = Job(id=uuid.uuid4().hex, user_id=current_user.id, title="Python Engineer", company="Corp", url="http://fake.com", description="Reqs: FastAPI", platform="LinkedIn", platform_job_id="1")
    base_resume_data = {
        "name": "Test User",
        "skills": ["Python", "PHP"],
        "experience": [
            {"title": "Backend Dev", "company": "Corp", "description": "Stuff"}
        ]
    }
    resume = Resume(
        id=uuid.uuid4().hex,
        user_id=current_user.id,
        name="Base CV",
        type="base",
        content_text=json.dumps(base_resume_data),
        file_path_pdf="/fake/path.pdf"
    )
    db_session.add(job)
    db_session.add(resume)
    await db_session.commit()
    
    # 2. Mock Router
    router = AsyncMock(spec=LLMTaskRouter)
    router.settings = AsyncMock()
    router.settings.heavy_model = "mocked-heavy"
    
    def complete_side_effect(task, **kwargs):
        if task == LLMTask.CV_TAILOR:
            # Check if this is a revision (prompt has 'USER INSTRUCTION')
            if "USER INSTRUCTION:" in kwargs.get("system_prompt", ""):
                return CVTailorOutput(changes=[ProposedChangeOutput(
                    target_type="inline",
                    target_reference="skills[0]",
                    section="skills",
                    original_text="Python",
                    proposed_text="Python/Django/FastAPI",
                    change_type=ChangeType.MODIFY,
                    reason="Revised per user instruction",
                    linked_requirement_ids=[],
                    linked_evidence_ids=[]
                )])
            return mock_tailor_output
        if task == LLMTask.CV_REVIEW:
            # We must map the change_ids dynamically based on what was inserted
            changes_json = kwargs.get('prompt').split("PROPOSED CHANGES:\n")[1]
            changes = json.loads(changes_json)
            out_reviews = []
            for i, c in enumerate(changes):
                if i < len(mock_review_output.reviews):
                    rev = mock_review_output.reviews[i]
                    out_reviews.append(ReviewDecisionOutput(
                        change_id=c['change_id'],
                        severity=rev.severity,
                        reason=rev.reason
                    ))
                else:
                    out_reviews.append(ReviewDecisionOutput(
                        change_id=c['change_id'],
                        severity=ReviewSeverity.SAFE,
                        reason="Safe"
                    ))
            return CVReviewOutput(reviews=out_reviews)
    
    router.complete_with_structured_output.side_effect = complete_side_effect
    
    # 3. Create Session
    session = await start_tailoring_session(db_session, current_user.id, job.id, resume.id, router)
    
    assert session.status == TailoringStatus.REVIEWING
    changes = (await db_session.execute(select(CVTailoringChange).where(CVTailoringChange.session_id == session.id))).scalars().all()
    all_changes = (await db_session.execute(select(CVTailoringChange))).scalars().all()
    print('ALL DB CHANGES:', all_changes)
    assert len(changes) == 3
    
    
    # 4. Check severities
    safe_change = next(c for c in changes if c.review_severity == ReviewSeverity.SAFE)
    blocked_change = next(c for c in changes if c.review_severity == ReviewSeverity.BLOCKED)
    warn_change = next(c for c in changes if c.review_severity == ReviewSeverity.WARNING)
    
    # 5. Make Decisions
    safe_change.user_decision = ReviewerStatus.ACCEPTED
    warn_change.user_decision = ReviewerStatus.ACCEPTED
    blocked_change.user_decision = ReviewerStatus.REJECTED
    await db_session.commit()
    
    # 6. Revise the safe change
    revised = await revise_change(db_session, current_user.id, session.id, safe_change.change_id, "Add Django too", router)
    assert revised.proposed_text == "Python/Django/FastAPI"
    
    await db_session.refresh(safe_change)
    assert safe_change.user_decision == ReviewerStatus.REJECTED # Old one rejected
    
    revised.user_decision = ReviewerStatus.ACCEPTED
    await db_session.commit()
    
    # 7. Finalize
    # Mock PDF generator and verifier
    with patch.object(DocumentGenerator, 'generate_resume') as mock_gen, \
         patch('app.services.tailoring.verify_pdf_document') as mock_verify, \
         patch('app.services.tailoring.persist_generated_document') as mock_persist, \
         patch('app.services.tailoring._build_resume_data_from_text') as mock_build:
         
         mock_gen.return_value = AsyncMock(pdf_path="/tmp/out.pdf", docx_path="/tmp/out.docx")
         mock_gen.return_value.pdf_path = "/tmp/out.pdf"
         mock_gen.return_value.docx_path = "/tmp/out.docx"
         
         mock_verify.return_value = AsyncMock()
         mock_verify.return_value.is_valid = True
         
         mock_persist.return_value = ("s3://pdf", "s3://docx")
         mock_build.return_value = base_resume_data
         
         final_resume = await finalize_session(db_session, current_user.id, session.id)
         
         assert final_resume.id != resume.id
         assert final_resume.base_resume_id == resume.id
         assert session.status == TailoringStatus.VERIFIED
         
         # Check content applied (Python/Django/FastAPI should be first skill, PHP removed)
         final_data = json.loads(final_resume.content_text)
         assert final_data['skills'][0] == "Python/Django/FastAPI"
         assert "PHP" not in final_data['skills']
         
         # Blocked change rejected -> title should remain Backend Dev
         assert final_data['experience'][0]['title'] == "Backend Dev"











