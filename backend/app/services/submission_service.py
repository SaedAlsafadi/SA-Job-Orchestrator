import os
import uuid
import structlog
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.application import Application, ApplicationRun
from app.models.enums import ApplicationStatus
from app.models.job import Job
from app.services.discovery_service import DiscoveryService
from app.services.question_engine import QuestionEngine
from app.core.llm.client import LLMClient
from playwright.async_api import async_playwright

logger = structlog.get_logger(__name__)

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
        else:
            from app.core.connectors.workable_app import WorkableApplicationConnector
            return WorkableApplicationConnector()

    async def approve_and_submit(self, user_id: str, application_id: str) -> str:
        """
        Entry point to authorize and trigger submission. 
        Returns the run ID of the submission attempt.
        """
        # Idempotency / Authorization check
        stmt = select(Application).join(Job).where(
            Application.id == application_id,
            Application.user_id == user_id
        )
        result = await self.db.execute(stmt)
        app = result.scalar_one_or_none()
        
        if not app:
            raise ValueError("Application not found or unauthorized.")
            
        if app.status in [ApplicationStatus.APPLIED, ApplicationStatus.SUBMITTING, ApplicationStatus.SUBMISSION_UNKNOWN]:
            raise ValueError(f"Application already in non-submittable state: {app.status}")
            
        if app.status != ApplicationStatus.WAITING_FOR_REVIEW:
            raise ValueError("Application must be in WAITING_FOR_REVIEW state to approve submission.")

        # Pre-flight capability check
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
        
        # In a real distributed system, we would enqueue a Celery/Arq job here.
        # For MVP, we run it synchronously and fail-closed if timeout.
        try:
            await self._execute_submission(app, job, run)
        except Exception as e:
            err_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            logger.error("Submission failed", error=err_msg)
            # Fail closed
            app.status = ApplicationStatus.SUBMISSION_BLOCKED
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.utcnow()
            await self.db.commit()
            
        return run_id

    async def _execute_submission(self, app: Application, job: Job, run: ApplicationRun):
        connector = await self._get_connector(job.url)
        
        # Re-load the last prep run to get tailored data
        stmt = select(ApplicationRun).where(
            ApplicationRun.application_id == app.id,
            ApplicationRun.status == "completed"
        ).order_by(ApplicationRun.completed_at.desc()).limit(1)
        prep_run = (await self.db.execute(stmt)).scalar_one_or_none()
        
        if not prep_run or not prep_run.state_data or "questions" not in prep_run.state_data:
            raise ValueError("Stale or missing preparation state.")
            
        resolved_data = prep_run.state_data["questions"]
        
        # Verify no high risk questions remain unapproved
        for q in resolved_data:
            if q.get("requires_human", False):
                raise ValueError(f"Unresolved high-risk question remains: {q.get('label')}")

        mock_profile = {"identity": {"first_name": "Test"}, "experience": [], "education": []} # In real app, fetch CandidateProfile
        
        os.makedirs("data/storage/screenshots", exist_ok=True)
        resume_path = app.cover_letter_path or "data/storage/mock_resume_test.pdf" # Mock for now
        
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
            # Map old prepared answers to new questions
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

    async def _execute_submission(self, app: Application, job: Job, run: ApplicationRun):
        connector = await self._get_connector(job.url)
        
        # Re-load the last prep run to get tailored data
        stmt = select(ApplicationRun).where(
            ApplicationRun.application_id == app.id,
            ApplicationRun.status == "completed"
        ).order_by(ApplicationRun.completed_at.desc()).limit(1)
        prep_run = (await self.db.execute(stmt)).scalar_one_or_none()
        
        if not prep_run or not prep_run.state_data or "questions" not in prep_run.state_data:
            raise ValueError("Stale or missing preparation state.")
            
        resolved_data = prep_run.state_data["questions"]
        
        # Verify no high risk questions remain unapproved
        for q in resolved_data:
            if q.get("requires_human", False):
                raise ValueError(f"Unresolved high-risk question remains: {q.get('label')}")

        mock_profile = {"identity": {"first_name": "Test"}, "experience": [], "education": []} # In real app, fetch CandidateProfile
        
        os.makedirs("data/storage/screenshots", exist_ok=True)
        resume_path = app.cover_letter_path or "data/storage/mock_resume_test.pdf" # Mock for now
        
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
