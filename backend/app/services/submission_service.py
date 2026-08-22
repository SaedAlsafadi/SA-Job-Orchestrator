import os
import uuid
import structlog
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationRun, ApplicationApproval
from app.models.enums import ApplicationStatus
from app.models.job import Job
from app.services.discovery_service import DiscoveryService
from app.services.question_engine import QuestionEngine
from app.core.llm.client import LLMClient
from playwright.async_api import async_playwright

logger = structlog.get_logger(__name__)

async def _pw_submission_task(connector, job_url, mock_profile, llm_client, resolved_data, resume_path, run_id):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # 1-3. Open application in fresh browser
            await connector.open_application(job_url, page)
            
            # 4. Inspect current form state
            current_questions = await connector.inspect_form(page)
            if not current_questions:
                raise ValueError("Application form could not be verified in fresh browser.")
            
            # 5-8. Reconstruct answers & verify
            engine = QuestionEngine(mock_profile, llm_client)
            re_resolved = await engine.resolve(current_questions)
            
            for fresh_q in re_resolved:
                if fresh_q.prefilled: continue
                
                # Find matching prepared answer
                matched_q = next((old_q for old_q in resolved_data if old_q["question_id"] == fresh_q.question_id), None)
                if matched_q and matched_q.get("answer"):
                    fresh_q.answer = matched_q["answer"]
                    fresh_q.requires_human = False
                
                if fresh_q.requires_human:
                    raise ValueError(f"Fresh browser encountered unapproved/new required question: {fresh_q.label}")
                    
            # Fill fields
            cv_present = await connector.detect_cv_presence(page)
            for q in re_resolved:
                if q.prefilled or q.requires_human: continue
                if q.input_type == "file" and "resume" in q.question_id.lower():
                    if not cv_present:
                        await connector.upload_resume(page, resume_path)
                elif q.answer:
                    await connector.answer_question(page, q)
            
            # 9. Final pre-submit screenshot
            os.makedirs("data/storage/screenshots", exist_ok=True)
            pre_screenshot = f"data/storage/screenshots/{run_id}_pre.png"
            await page.screenshot(path=pre_screenshot)
            
            # 10-11. Submit
            is_live = os.getenv("ENABLE_LIVE_SUBMISSION", "false").lower() == "true"
            conf_msg = ""
            conf_error = None
            if not is_live:
                logger.info("ENABLE_LIVE_SUBMISSION is false. Bypassing actual submit click.")
                conf_msg = "Mock submission success (live submission disabled)"
            else:
                logger.warning("LIVE SUBMISSION ENABLED. Executing actual submit.")
                await connector.submit(page)
                
                # 12. Confirm
                try:
                    conf_msg = await connector.capture_confirmation(page)
                except Exception as e:
                    conf_error = str(e)
            
            post_screenshot = f"data/storage/screenshots/{run_id}_post.png"
            await page.screenshot(path=post_screenshot)
            
            return {
                "conf_msg": conf_msg,
                "conf_error": conf_error,
                "pre_screenshot": pre_screenshot,
                "post_screenshot": post_screenshot
            }
            
        finally:
            await browser.close()


class SubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.discovery = DiscoveryService(db)
        self.llm_client = LLMClient()

    async def _get_connector(self, url: str):
        if "lever" in url:
            from app.core.connectors.lever_app import LeverApplicationConnector
            return LeverApplicationConnector()
        elif "greenhouse" in url:
            from app.core.connectors.greenhouse_app import GreenhouseApplicationConnector
            return GreenhouseApplicationConnector()
        elif "workable" in url:
            from app.core.connectors.workable_app import WorkableApplicationConnector
            return WorkableApplicationConnector()
        raise ValueError(f"No connector handles URL: {url}")

    async def approve_application(self, user_id: str, application_id: str) -> str:
        """
        Creates a single-use human approval record.
        Idempotent: Re-approving an already approved application returns the existing approval ID.
        """
        # Load app
        stmt = select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id
        )
        app = (await self.db.execute(stmt)).scalar_one_or_none()
        if not app:
            raise ValueError("Application not found or unauthorized.")
            
        if app.status != ApplicationStatus.WAITING_FOR_REVIEW:
            raise ValueError(f"Application must be in WAITING_FOR_REVIEW state. Current: {app.status}")
            
        # Get latest run
        run_stmt = select(ApplicationRun).where(
            ApplicationRun.application_id == app.id,
            ApplicationRun.status == "completed"
        ).order_by(ApplicationRun.completed_at.desc()).limit(1)
        prep_run = (await self.db.execute(run_stmt)).scalar_one_or_none()
        
        if not prep_run:
            raise ValueError("No preparation run found for this application.")
            
        # Check idempotency
        approval_stmt = select(ApplicationApproval).where(
            ApplicationApproval.application_id == app.id,
            ApplicationApproval.used_at.is_(None),
            ApplicationApproval.expires_at > datetime.utcnow()
        )
        existing_approval = (await self.db.execute(approval_stmt)).scalar_one_or_none()
        if existing_approval:
            return existing_approval.id
            
        # Create approval
        approval = ApplicationApproval(
            id=f"appr_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            application_id=app.id,
            application_run_id=prep_run.id,
            job_id=app.job_id,
            candidate_profile_version=1, # FIXME: get real version from CandidateProfile logic
            platform="workable", # FIXME: dynamic
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        self.db.add(approval)
        await self.db.commit()
        return approval.id

    async def approve_and_submit(self, user_id: str, application_id: str) -> str:
        """
        Consumes an approval and triggers the submission workflow.
        Returns the run ID.
        """
        # Load app
        stmt = select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id
        )
        app = (await self.db.execute(stmt)).scalar_one_or_none()
        if not app:
            raise ValueError("Application not found or unauthorized.")
            
        if app.status in [ApplicationStatus.SUBMITTING, ApplicationStatus.APPLIED, ApplicationStatus.SUBMISSION_UNKNOWN]:
            raise ValueError(f"Application already in non-submittable state: {app.status}")
            
        if app.status != ApplicationStatus.WAITING_FOR_REVIEW:
            raise ValueError("Application must be in WAITING_FOR_REVIEW state to approve submission.")
            
        # Check for approval
        approval_stmt = select(ApplicationApproval).where(
            ApplicationApproval.application_id == app.id,
            ApplicationApproval.used_at.is_(None),
            ApplicationApproval.expires_at > datetime.utcnow()
        ).with_for_update()
        
        approval = (await self.db.execute(approval_stmt)).scalar_one_or_none()
        if not approval:
            raise ValueError("No valid unused human approval found for this application.")
            
        # Consume approval
        approval.used_at = datetime.utcnow()
        
        # Check global LIVE_SUBMISSION flag
        is_live = os.getenv("ENABLE_LIVE_SUBMISSION", "false").lower() == "true"
        if not is_live:
            raise ValueError("ENABLE_LIVE_SUBMISSION is false. Submission blocked.")

        job = await self.db.get(Job, app.job_id)
        source_connector = self.discovery._get_source(job.url)
        caps = source_connector.capabilities()
        if not caps.submission:
            raise ValueError(f"Connector {source_connector.name()} reports submission=False.")
            
        # Create submission attempt run
        run_id = f"sub_{uuid.uuid4().hex[:12]}"
        run = ApplicationRun(
            id=run_id,
            user_id=app.user_id,
            application_id=application_id,
            status="submitting",
            started_at=datetime.utcnow()
        )
        self.db.add(run)
        app.status = ApplicationStatus.SUBMITTING
        await self.db.commit()
        
        # Execute
        try:
            await self._execute_submission(app, job, run, approval.application_run_id)
        except Exception as e:
            err_msg = str(e).encode("ascii", "ignore").decode("ascii")
            logger.error("Submission failed", error=err_msg)
            app.status = ApplicationStatus.SUBMISSION_BLOCKED
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.utcnow()
            await self.db.commit()
            
        return run_id

    async def _execute_submission(self, app: Application, job: Job, run: ApplicationRun, prep_run_id: str):
        connector = await self._get_connector(job.url)
        
        # Load prep run
        prep_run = await self.db.get(ApplicationRun, prep_run_id)
        if not prep_run or not prep_run.state_data or "questions" not in prep_run.state_data:
            raise ValueError("Stale or missing preparation state.")
            
        resolved_data = prep_run.state_data["questions"]
        
        # Verify no high risk questions remain unapproved
        for q in resolved_data:
            if q.get("requires_human", False):
                raise ValueError(f"Unresolved high-risk question remains: {q.get('label')}")

        from app.models.candidate_profile import CandidateProfile
        cp = (await self.db.execute(select(CandidateProfile).where(CandidateProfile.user_id == app.user_id))).scalar_one_or_none()
        mock_profile = {
            "identity": cp.identity,
            "location": cp.location,
            "employment": cp.employment,
            "education": cp.education,
            "experience": cp.experience,
            "skills": cp.skills,
        } if cp else {"identity": {"first_name": "Test"}, "experience": [], "education": []}
        
        resume_path = app.cover_letter_path
        if not resume_path or not os.path.exists(resume_path):
            raise ValueError("Prepared CV does not exist.")
            
        from app.core.pw_utils import run_playwright_in_thread
        res = await run_playwright_in_thread(_pw_submission_task, connector, job.url, mock_profile, self.llm_client, resolved_data, resume_path, run.id)
        
        if res.get("conf_error"):
            app.status = ApplicationStatus.SUBMISSION_UNKNOWN
            run.status = "unknown"
            run.error = "Confirmation failed: " + res["conf_error"]
            run.completed_at = datetime.utcnow()
            await self.db.commit()
            return
            
        app.status = ApplicationStatus.APPLIED
        app.applied_at = datetime.utcnow()
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.artifacts = {
            "pre_screenshot": res["pre_screenshot"],
            "post_screenshot": res["post_screenshot"],
            "confirmation": res["conf_msg"]
        }
        await self.db.commit()
