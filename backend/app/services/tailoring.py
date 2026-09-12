import asyncio
import uuid
from datetime import datetime, UTC
from difflib import SequenceMatcher
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


def _rejected_novel_fragments(change: CVTailoringChange) -> list[str]:
    """Return only text introduced by a rejected proposal.

    A modified proposal commonly starts with the original sentence. Treating
    that shared prefix as forbidden makes an unchanged, correctly rejected CV
    fail integrity verification. Removed text has no introduced fragment.
    """
    proposed = (change.proposed_text or "").strip()
    if not proposed:
        return []
    original = (change.original_text or "").strip()
    if not original:
        return [proposed]

    original_words = original.split()
    proposed_words = proposed.split()
    fragments: list[str] = []
    for tag, _i1, _i2, j1, j2 in SequenceMatcher(
        None, original_words, proposed_words
    ).get_opcodes():
        if tag in {"insert", "replace"}:
            fragment = " ".join(proposed_words[j1:j2]).strip()
            if len(fragment) >= 8:
                fragments.append(fragment)
    return fragments


async def get_or_create_revision_session(
    db: AsyncSession,
    user_id: str,
    resume_id: str,
) -> CVTailoringSession:
    """Open a workbench session for a tailored résumé without invoking a model.

    Older tailored résumés were generated before session lineage was persisted.
    For those records we create an empty review session whose immutable source is
    the selected tailored résumé. Generating suggestions remains an explicit,
    model-backed action from inside the workbench.
    """
    resume = (
        await db.execute(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )
    ).scalar_one_or_none()
    if resume is None:
        raise ValueError("Résumé not found")
    if resume.type != "tailored" or not resume.job_id:
        raise ValueError("Only a tailored résumé with a target job can be revised")

    existing = (
        await db.execute(
            select(CVTailoringSession)
            .where(
                CVTailoringSession.user_id == user_id,
                (
                    (CVTailoringSession.final_resume_id == resume.id)
                    | (
                        (CVTailoringSession.base_resume_id == resume.id)
                        & (CVTailoringSession.status == TailoringStatus.REVIEWING)
                    )
                ),
            )
            .order_by(CVTailoringSession.updated_at.desc())
        )
    ).scalars().first()
    if existing is not None:
        return existing

    session = CVTailoringSession(
        user_id=user_id,
        job_id=resume.job_id,
        # The selected immutable tailored version is the source for revision;
        # finalization creates a new résumé rather than overwriting it.
        base_resume_id=resume.id,
        base_resume_version=resume.updated_at.isoformat() if resume.updated_at else None,
        status=TailoringStatus.REVIEWING,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def start_tailoring_session(
    db: AsyncSession,
    user_id: str,
    job_id: str,
    base_resume_id: str,
    router: LLMTaskRouter,
    candidate_profile_version: str | None = None,
    language: str = "en",
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
    # Persist the session before the network call.  Keeping an uncommitted SQLite
    # write transaction open while the model runs prevents the independent usage
    # tracker from recording the call ("database is locked").
    await db.commit()
    
    # 2. AI Pass 1: Tailor
    system_prompt_tailor = f"""
You are a CV Tailoring engine. Your job is to propose discrete changes to a candidate's CV to better match the given job.
DO NOT INVENT FACTS. Each change MUST be supported by candidate evidence.

ALL proposed texts and reasons MUST be written in {language}.
"""
    
    from app.services.resume_text import normalize_resume_text

    prompt_tailor = (
        f"JOB:\n{job.title} - {job.description}\n\n"
        f"CV:\n{normalize_resume_text(resume.content_text or '')}\n"
    )
    
    try:
        tailor_result = await router.complete_with_structured_output(
            task=LLMTask.CV_TAILOR,
            prompt=prompt_tailor,
            system_prompt=system_prompt_tailor,
            output_schema=CVTailorOutput,
            max_tokens=8192,
        )
    except asyncio.CancelledError:
        # A browser disconnect/timeout must not strand a session in REVIEWING.
        session.status = TailoringStatus.FAILED
        await asyncio.shield(db.commit())
        raise
    except Exception as e:
        logger.error("Tailoring failed", error=str(e))
        session.status = TailoringStatus.FAILED
        await db.commit()
        await db.refresh(session)
        return session

    # Save the proposed changes and release the write lock before AI Pass 2.
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
            review_severity=ReviewSeverity.SAFE,
        )
        db.add(db_change)
    await db.commit()

    changes_list = (
        await db.execute(
            select(CVTailoringChange).where(CVTailoringChange.session_id == session.id)
        )
    ).scalars().all()
    # The SELECT above opens a new implicit transaction. Close it before the
    # second network call as well; mapped objects remain usable because the
    # application session factory sets expire_on_commit=False.
    await db.commit()

    if changes_list:
        try:
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
            
            prompt_review = f"BASE CV:\n{normalize_resume_text(resume.content_text or '')}\n\nPROPOSED CHANGES:\n{changes_json}"
            
            review_result = await router.complete_with_structured_output(
                task=LLMTask.CV_REVIEW,
                prompt=prompt_review,
                system_prompt=system_prompt_review,
                output_schema=CVReviewOutput,
                max_tokens=8192,
            )
            
            # Map review results
            review_map = {r.change_id: r for r in review_result.reviews}
            for c in changes_list:
                if c.change_id in review_map:
                    c.review_severity = review_map[c.change_id].severity
                    c.review_reason = review_map[c.change_id].reason
                else:
                    c.review_severity = ReviewSeverity.BLOCKED
                    c.review_reason = "The independent review did not return a verdict for this change."
        except Exception as e:
            # The tailoring suggestions are still useful input for a human review,
            # but an unavailable/malformed safety review must fail closed.  Keeping
            # the session REVIEWING also preserves the original-CV preview and lets
            # the user reject every proposal instead of losing the whole run.
            logger.error("Tailoring review failed; blocking all changes", error=str(e))
            for c in changes_list:
                c.review_severity = ReviewSeverity.BLOCKED
                c.review_reason = "Independent AI review unavailable; reject or revise this change manually."

    await db.commit()
    await db.refresh(session)
    return session

from app.services.tailoring_merge import merge_tailoring_changes
from app.services.resume import _build_resume_data_from_text, persist_generated_document
from app.services.resume_text import normalize_resume_text
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
    if base_resume is None:
        raise ValueError("Base resume not found")

    accepted = [c for c in session.changes if c.user_decision == ReviewerStatus.ACCEPTED]
    if not accepted:
        # A zero-change result should be byte-faithful to the uploaded CV. Rebuilding
        # it from extracted text can lose layout and even split words/bullets. The
        # new Resume row is still an immutable, job-specific version; it simply
        # references the same immutable source artifacts.
        new_resume = Resume(
            user_id=user_id,
            name=f"Tailored - {base_resume.name}",
            type="tailored",
            template_id=base_resume.template_id,
            base_resume_id=base_resume.id,
            job_id=session.job_id,
            file_path_pdf=base_resume.file_path_pdf,
            file_path_docx=base_resume.file_path_docx,
            content_text=base_resume.content_text,
            audit_metadata={
                "tailoring_session_id": session.id,
                "accepted_change_count": 0,
                "artifact_strategy": "preserve_base_artifact",
            },
        )
        db.add(new_resume)
        await db.flush()
        session.final_resume_id = new_resume.id
        session.status = TailoringStatus.VERIFIED
        await db.commit()
        await db.refresh(new_resume)
        return new_resume

    # Parse structured doc
    base_dict = _build_resume_data_from_text(base_resume.content_text or "")
    base_doc = TailoredResumeData.model_validate(base_dict)
    
    # Merge accepted changes
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
        # Phase 19.5 integrity verification: sections present in the BASE doc
        # must survive; accepted changes must appear; rejected ones must not.
        base_sections = [
            label
            for label, attr in (
                ("Experience", "experience"), ("Projects", "projects"),
                ("Skills", "skills"), ("Education", "education"),
                ("Certifications", "certifications"),
                ("Professional Summary", "summary"),
            )
            if getattr(base_doc, attr)
        ]
        accepted_texts = [c.proposed_text or "" for c in accepted]
        rejected_texts = [
            fragment
            for c in session.changes
            if c.user_decision == ReviewerStatus.REJECTED
            for fragment in _rejected_novel_fragments(c)
        ]
        verification = verify_pdf_document(
            doc_res.pdf_path,
            expected_name=new_doc.name,
            expected_sections=base_sections,
            required_texts=accepted_texts,
            forbidden_texts=rejected_texts,
            base_text=normalize_resume_text(base_resume.content_text or ""),
        )
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
    router: LLMTaskRouter,
    language: str = "en",
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
    system_prompt_revise = f"""
You are a CV Tailoring engine revising a specific proposal.
USER INSTRUCTION: {instruction}

You must output exactly ONE proposed change that updates or replaces the previous proposal.
DO NOT INVENT FACTS.

ALL proposed texts and reasons MUST be written in {language}.
"""
    
    from app.services.resume_text import normalize_resume_text

    prompt_revise = (
        f"JOB:\n{job.description}\n\n"
        f"ORIGINAL CV:\n{normalize_resume_text(base_resume.content_text or '')}\n\n"
        f"PREVIOUS PROPOSAL:\nTarget: {change.target_reference}\n"
        f"Original Text: {change.original_text}\n"
        f"Proposed Text: {change.proposed_text}\nReason: {change.reason}"
    )
    
    try:
        tailor_result = await router.complete_with_structured_output(
            task=LLMTask.CV_TAILOR,
            prompt=prompt_revise,
            system_prompt=system_prompt_revise,
            output_schema=CVTailorOutput,
            max_tokens=8192,
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
        
        prompt_review = f"BASE CV:\n{normalize_resume_text(base_resume.content_text or '')}\n\nPROPOSED CHANGES:\n{changes_json}"
        
        review_result = await router.complete_with_structured_output(
            task=LLMTask.CV_REVIEW,
            prompt=prompt_review,
            system_prompt=system_prompt_review,
            output_schema=CVReviewOutput,
            max_tokens=8192,
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

