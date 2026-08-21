import asyncio
import os
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from app.db.session import async_session_factory
from app.services.submission_service import SubmissionService
from app.models.application import Application, ApplicationRun
from app.models.job import Job
from app.models.enums import ApplicationStatus
from app.core.connectors.workable_app import WorkableApplicationConnector

async def setup_test_data(db, url: str) -> str:
    # 1. Clear previous
    from sqlalchemy import delete
    await db.execute(delete(ApplicationRun).where(ApplicationRun.application_id == "live_app_1"))
    await db.execute(delete(Application).where(Application.id == "live_app_1"))
    await db.execute(delete(Job).where(Job.id == "live_job_1"))
    await db.commit()
    
    job = Job(
        id="live_job_1",
        user_id="testuser0000000000000000000000aa",
        title="Live Submission Test Job",
        company="Test Company",
        platform="workable",
        platform_job_id="live_1",
        url=url
    )
    app = Application(
        id="live_app_1",
        user_id="testuser0000000000000000000000aa",
        job_id="live_job_1",
        status=ApplicationStatus.WAITING_FOR_REVIEW
    )
    run = ApplicationRun(
        id="prep_run_1",
        user_id="testuser0000000000000000000000aa",
        application_id="live_app_1",
        status="completed",
        state_data={
            "resolved_questions": [
                {"question_id": "firstname", "label": "First name", "answer": "Test", "prefilled": False},
                {"question_id": "lastname", "label": "Last name", "answer": "User", "prefilled": False},
                {"question_id": "email", "label": "Email", "answer": "test@example.com", "prefilled": False},
            ]
        }
    )
    db.add(job)
    db.add(app)
    db.add(run)
    await db.commit()
    return app.id

async def run_live_submission(url: str):
    print("=== LIVE WORKABLE SUBMISSION TEST ===")
    print(f"Target URL: {url}")
    
    is_live = os.getenv("ENABLE_LIVE_SUBMISSION", "false").lower() == "true"
    if not is_live:
        print("\nENABLE_LIVE_SUBMISSION is false. Exiting to prevent accidental submission.")
        return

    print("\n[SUMMARY]")
    print("Platform: Workable")
    print("Candidate: Test User (test@example.com)")
    print("WARNING: This will ACTUALLY SUBMIT an application to the employer.")
    
    if os.getenv("AUTO_CONFIRM", "false").lower() != "true":
        confirm = input("\nType 'SUBMIT' to confirm and proceed: ")
        if confirm != "SUBMIT":
            print("Aborted.")
            return
    else:
        print("\nAUTO_CONFIRM is true. Proceeding automatically.")
        
    async with async_session_factory() as db:
        app_id = await setup_test_data(db, url)
        svc = SubmissionService(db)
        print("\nStarting submission service...")
        run_id = await svc.approve_and_submit("testuser0000000000000000000000aa", app_id)
        
        # Verify result
        app = await db.get(Application, app_id)
        run = await db.get(ApplicationRun, run_id)
        
        print(f"\nFinal Application State: {app.status}")
        print(f"Run State: {run.status}")
        if run.error:
            print(f"Run Error: {run.error}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Public Workable Job URL")
    args = parser.parse_args()
    asyncio.run(run_live_submission(args.url))
