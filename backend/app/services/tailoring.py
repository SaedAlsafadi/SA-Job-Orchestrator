import uuid
from datetime import datetime, UTC
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any
import json

from app.models.tailoring import CVTailoringSession, CVTailoringChange
from app.models.enums import TailoringStatus, ChangeType, ReviewerStatus, ReviewSeverity
from app.models.resume import Resume
from app.models.job import Job
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.schemas.tailoring import CVTailorOutput, CVReviewOutput

logger = structlog.get_logger(__name__)

async def start_tailoring_session(
    db: AsyncSession,
    user_id: str,
    job_id: str,
    base_resume_id: str,
    router: LLMTaskRouter,
    candidate_profile_version: str | None = None,
) -> CVTailoringSession:
    """Start a new CV tailoring session."""
    
    # 1. Fetch data
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    resume = (await db.execute(select(Resume).where(Resume.id == base_resume_id))).scalar_one_or_none()
    
    if not job or not resume:
        raise ValueError("Job or Resume not found")
        
    if job.user_id != user_id or resume.user_id != user_id:
        raise ValueError("Unauthorized access")
        
    # Create session
    session = CVTailoringSession(
        user_id=user_id,
        job_id=job_id,
        base_resume_id=base_resume_id,
        candidate_profile_version=candidate_profile_version,
        status=TailoringStatus.REVIEWING,
        tailor_model=router.settings.heavy_model,
        review_model=router.settings.heavy_model,
    )
    db.add(session)
    await db.flush()
    
    # 2. AI Pass 1: Tailor
    system_prompt_tailor = """
You are a CV Tailoring engine. Your job is to propose discrete changes to a candidate's CV to better match the given job.
DO NOT INVENT FACTS. Each change MUST be supported by candidate evidence.
"""
    
    prompt_tailor = f"JOB:\n{job.title} - {job.description}\n\nCV:\n{resume.content_text}\n"
    
    try:
        tailor_result = await router.complete_with_structured_output(
            task=LLMTask.CV_TAILOR,
            prompt=prompt_tailor,
            system_prompt=system_prompt_tailor,
            output_schema=CVTailorOutput
        )
        
        # Save changes to DB
        for change in tailor_result.changes:
            db_change = CVTailoringChange(
                session_id=session.id,
                user_id=user_id,
                change_id=uuid.uuid4().hex,
                target_type=change.target_type,
                target_reference=change.target_reference,
                section=change.section,
                original_text=change.original_text,
                proposed_text=change.proposed_text,
                change_type=change.change_type,
                reason=change.reason,
                linked_requirement_ids=change.linked_requirement_ids,
                linked_evidence_ids=change.linked_evidence_ids,
                user_decision=ReviewerStatus.PENDING,
                review_severity=ReviewSeverity.SAFE
            )
            db.add(db_change)
            
        await db.flush()
        
        # 3. AI Pass 2: Review
        changes_list = (await db.execute(select(CVTailoringChange).where(CVTailoringChange.session_id == session.id))).scalars().all()
        if changes_list:
            system_prompt_review = """
You are an independent CV Review AI. Check the proposed changes against the candidate's base CV.
Flag ANY changes that hallucinate experience, invent skills, or exaggerate seniority as BLOCKED.
Flag minor style issues or ambiguous claims as WARNING.
Otherwise mark SAFE.
"""
            changes_json = json.dumps([{
                "change_id": c.change_id, 
                "original": c.original_text, 
                "proposed": c.proposed_text,
                "reason": c.reason
            } for c in changes_list])
            
            prompt_review = f"BASE CV:\n{resume.content_text}\n\nPROPOSED CHANGES:\n{changes_json}"
            
            review_result = await router.complete_with_structured_output(
                task=LLMTask.CV_REVIEW,
                prompt=prompt_review,
                system_prompt=system_prompt_review,
                output_schema=CVReviewOutput
            )
            
            # Map review results
            review_map = {r.change_id: r for r in review_result.reviews}
            for c in changes_list:
                if c.change_id in review_map:
                    c.review_severity = review_map[c.change_id].severity
                    c.review_reason = review_map[c.change_id].reason
                    
    except Exception as e:
        logger.error("Tailoring failed", error=str(e))
        session.status = TailoringStatus.FAILED
        
    await db.commit()
    await db.refresh(session)
    return session

from app.services.tailoring_merge import merge_tailoring_changes
from app.services.resume import _build_resume_data_from_text, persist_generated_document
from app.core.documents.generator import DocumentGenerator
from app.services.pdf_verifier import verify_pdf_document
from app.core.llm.prompts.resume_tailor import TailoredResumeData

async def finalize_session(
    db: AsyncSession,
    user_id: str,
    session_id: str
) -> Resume:
    """Finalize session and create new Resume object."""
    # Fetch session
    result = await db.execute(select(CVTailoringSession).where(
        CVTailoringSession.id == session_id,
        CVTailoringSession.user_id == user_id
    ))
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError("Session not found")
        
    await db.refresh(session, ["changes"])
    
    # Validation
    for c in session.changes:
        if c.user_decision == ReviewerStatus.PENDING:
            raise ValueError(f"Change {c.change_id} is pending")
        if c.user_decision == ReviewerStatus.ACCEPTED and c.review_severity == ReviewSeverity.BLOCKED:
            raise ValueError(f"Change {c.change_id} is blocked but accepted")
            
    base = await db.execute(select(Resume).where(Resume.id == session.base_resume_id))
    base_resume = base.scalar_one_or_none()
    
    # Parse structured doc
    base_dict = _build_resume_data_from_text(base_resume.content_text or "")
    base_doc = TailoredResumeData.model_validate(base_dict)
    
    # Merge accepted changes
    accepted = [c for c in session.changes if c.user_decision == ReviewerStatus.ACCEPTED]
    try:
        new_doc = merge_tailoring_changes(base_doc, accepted)
    except Exception as e:
        session.status = TailoringStatus.FAILED
        await db.commit()
        raise ValueError(f"Merge conflict: {e}")
        
    session.status = TailoringStatus.RENDERING
    await db.commit()
    
    # Render PDF
    generator = DocumentGenerator(llm_client=None)
    job_result = await db.execute(select(Job).where(Job.id == session.job_id))
    job = job_result.scalar_one_or_none()
    
    doc_res = await generator.generate_resume(
        resume_data=new_doc.model_dump(),
        job_description=job.description if job else "",
        template_name=base_resume.template_id,
        formats=["pdf", "docx"],
    )
    
    if doc_res.pdf_path:
        verification = verify_pdf_document(doc_res.pdf_path, expected_name=new_doc.name)
        if not verification.is_valid:
            session.status = TailoringStatus.FAILED
            await db.commit()
            raise ValueError(f"PDF Verification failed: {verification.reason}")
            
    pdf_key, docx_key = await persist_generated_document(user_id, doc_res)
    
    new_resume = Resume(
        user_id=user_id,
        name=f"Tailored - {base_resume.name}",
        type="tailored",
        template_id=base_resume.template_id,
        base_resume_id=base_resume.id,
        job_id=session.job_id,
        file_path_pdf=pdf_key,
        file_path_docx=docx_key,
        content_text=new_doc.model_dump_json(),
    )
    db.add(new_resume)
    await db.flush()
    
    session.final_resume_id = new_resume.id
    session.status = TailoringStatus.VERIFIED
    await db.commit()
    await db.refresh(new_resume)
    
    return new_resume

async def regenerate_session(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    router: LLMTaskRouter
) -> CVTailoringSession:
    """Regenerate tailoring session proposals."""
    # Fetch old session
    result = await db.execute(select(CVTailoringSession).where(
        CVTailoringSession.id == session_id,
        CVTailoringSession.user_id == user_id
    ))
    old_session = result.scalar_one_or_none()
    if not old_session:
        raise ValueError("Session not found")
        
    return await start_tailoring_session(
        db, user_id, old_session.job_id, old_session.base_resume_id, router, old_session.candidate_profile_version
    )




async def revise_change(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    change_id: str,
    instruction: str,
    router: LLMTaskRouter
) -> CVTailoringChange:
    """Revise a specific change with instructions."""
    # Fetch session and change
    session = (await db.execute(select(CVTailoringSession).where(
        CVTailoringSession.id == session_id,
        CVTailoringSession.user_id == user_id
    ))).scalar_one_or_none()
    
    if not session:
        raise ValueError("Session not found")
        
    change = (await db.execute(select(CVTailoringChange).where(
        CVTailoringChange.session_id == session_id,
        CVTailoringChange.change_id == change_id
    ))).scalar_one_or_none()
    
    if not change:
        raise ValueError("Change not found")
        
    base_resume = (await db.execute(select(Resume).where(Resume.id == session.base_resume_id))).scalar_one_or_none()
    job = (await db.execute(select(Job).where(Job.id == session.job_id))).scalar_one_or_none()
    
    if not base_resume or not job:
        raise ValueError("Source documents missing")
        
    # 1. AI Pass 1: Revise Tailor
    system_prompt_revise = """
You are a CV Tailoring engine revising a specific proposal.
USER INSTRUCTION: {instruction}

You must output exactly ONE proposed change that updates or replaces the previous proposal.
DO NOT INVENT FACTS.
""".replace("{instruction}", instruction)
    
    prompt_revise = f"JOB:\n{job.description}\n\nORIGINAL CV:\n{base_resume.content_text}\n\nPREVIOUS PROPOSAL:\nTarget: {change.target_reference}\nOriginal Text: {change.original_text}\nProposed Text: {change.proposed_text}\nReason: {change.reason}"
    
    try:
        tailor_result = await router.complete_with_structured_output(
            task=LLMTask.CV_TAILOR,
            prompt=prompt_revise,
            system_prompt=system_prompt_revise,
            output_schema=CVTailorOutput
        )
        
        if not tailor_result.changes:
            raise ValueError("LLM returned no changes for revision")
            
        new_c = tailor_result.changes[0]
        
        new_db_change = CVTailoringChange(
            session_id=session.id,
            user_id=user_id,
            change_id=uuid.uuid4().hex,
            target_type=new_c.target_type,
            target_reference=new_c.target_reference,
            section=new_c.section,
            original_text=new_c.original_text,
            proposed_text=new_c.proposed_text,
            change_type=new_c.change_type,
            reason=new_c.reason,
            linked_requirement_ids=new_c.linked_requirement_ids,
            linked_evidence_ids=new_c.linked_evidence_ids,
            user_decision=ReviewerStatus.PENDING,
            review_severity=ReviewSeverity.SAFE
        )
        db.add(new_db_change)
        await db.flush()
        
        # 2. AI Pass 2: Review
        system_prompt_review = """
You are an independent CV Review AI. Check the revised change against the candidate's base CV.
Flag ANY changes that hallucinate experience, invent skills, or exaggerate seniority as BLOCKED.
Flag minor style issues or ambiguous claims as WARNING.
Otherwise mark SAFE.
"""
        changes_json = json.dumps([{
            "change_id": new_db_change.change_id, 
            "original": new_db_change.original_text, 
            "proposed": new_db_change.proposed_text,
            "reason": new_db_change.reason
        }])
        
        prompt_review = f"BASE CV:\n{base_resume.content_text}\n\nPROPOSED CHANGES:\n{changes_json}"
        
        review_result = await router.complete_with_structured_output(
            task=LLMTask.CV_REVIEW,
            prompt=prompt_review,
            system_prompt=system_prompt_review,
            output_schema=CVReviewOutput
        )
        
        if review_result.reviews:
            r = review_result.reviews[0]
            new_db_change.review_severity = r.severity
            new_db_change.review_reason = r.reason
            
        # Mark old as rejected
        change.user_decision = ReviewerStatus.REJECTED
        await db.commit()
        await db.refresh(new_db_change)
        
        return new_db_change
        
    except Exception as e:
        logger.error("Revision failed", error=str(e))
        raise ValueError(f"Revision failed: {e}")

