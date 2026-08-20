from playwright.async_api import async_playwright
import structlog
import traceback
import json
import os
from datetime import datetime

logger = structlog.get_logger(__name__)

async def run_application_preparation(run_id: str, app_id: str, job_url: str, db_session_maker, profile_data: dict, resume_path: str):
    """Background task to run playwright without holding HTTP request open."""
    async with db_session_maker() as db:
        try:
            from app.core.connectors.workable_app import WorkableApplicationConnector
            from app.core.connectors.greenhouse_app import GreenhouseApplicationConnector
            from app.core.connectors.lever_app import LeverApplicationConnector
            from app.services.question_engine import QuestionEngine
            from app.core.llm.client import LLMClient
            from sqlalchemy import update
            from app.models.application import ApplicationRun, Application
            
            if "lever" in job_url:
                connector = LeverApplicationConnector()
            elif "greenhouse" in job_url:
                connector = GreenhouseApplicationConnector()
            else:
                connector = WorkableApplicationConnector()
                
            engine = QuestionEngine(profile_data, LLMClient())
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await connector.open_application(job_url, page)
                
                questions = await connector.inspect_form(page)
                resolved = await engine.resolve(questions)
                
                cv_present = await connector.detect_cv_presence(page)
                
                for q in resolved:
                    if q.prefilled or q.requires_human:
                        continue
                        
                    if q.input_type == "file" and "resume" in q.question_id.lower():
                        if cv_present:
                            logger.info("CV is already present on the platform, skipping automatic upload.")
                        elif resume_path:
                            await connector.upload_resume(page, resume_path)
                    else:
                        await connector.answer_question(page, q)
                
                # Take screenshot
                screenshot_path = f"data/storage/screenshots/{run_id}.png"
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                await page.screenshot(path=screenshot_path)
                
                state = await connector.capture_state(page)
                state["screenshot"] = screenshot_path
                state["questions"] = [q.model_dump() for q in resolved]
                state["cv_present"] = cv_present
                state["cv_replacement_recommended"] = cv_present  # For human review
                
                await browser.close()
                
                stmt = update(ApplicationRun).where(ApplicationRun.id == run_id).values(
                    status="completed",
                    state_data=state,
                    completed_at=datetime.utcnow()
                )
                await db.execute(stmt)
                
                stmt2 = update(Application).where(Application.id == app_id).values(
                    status="waiting_for_review"
                )
                await db.execute(stmt2)
                await db.commit()
                
        except Exception as e:
            logger.error("Preparation failed", error=str(e))
            from app.models.application import ApplicationRun, Application
            from sqlalchemy import update
            stmt = update(ApplicationRun).where(ApplicationRun.id == run_id).values(
                status="failed",
                error=traceback.format_exc(),
                completed_at=datetime.utcnow()
            )
            await db.execute(stmt)
            
            stmt2 = update(Application).where(Application.id == app_id).values(
                status="failed"
            )
            await db.execute(stmt2)
            await db.commit()
