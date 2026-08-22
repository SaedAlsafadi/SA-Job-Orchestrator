import os
import pytest
import asyncio
from sqlalchemy import select, text
from app.db.session import async_session_factory
from app.db.tenant import current_user_id

from app.models.application import Application, ApplicationRun
from app.models.enums import ApplicationStatus
from app.services.submission_service import SubmissionService

@pytest.mark.asyncio
async def test_real_workable_submission(monkeypatch):
    is_live = os.getenv("ENABLE_LIVE_SUBMISSION", "false").lower() == "true"
    if not is_live:
        pytest.skip("ENABLE_LIVE_SUBMISSION is not true. Skipping live test.")

    current_user_id.set("test-e2e-user")
    
    async def mock_pw_task(*args, **kwargs):
        return {
            "conf_msg": "Application submitted successfully",
            "conf_error": None,
            "pre_screenshot": "data/storage/screenshots/mock_pre.png",
            "post_screenshot": "data/storage/screenshots/mock_post.png"
        }
        
    import app.services.submission_service
    monkeypatch.setattr(app.services.submission_service, "_pw_submission_task", mock_pw_task)

    async with async_session_factory() as db:
        stmt = select(Application).where(Application.status == ApplicationStatus.WAITING_FOR_REVIEW).limit(1)
        app_record = (await db.execute(stmt)).scalar_one_or_none()
        
        if not app_record:
            pytest.skip("No application in WAITING_FOR_REVIEW state found.")
            
        print(f"Targeting Application ID: {app_record.id}")
        
        service = SubmissionService(db)
        
        # Approve
        approval_id = await service.approve_application(app_record.user_id, app_record.id)
        assert approval_id.startswith("appr_")
        
        # Submit
        run_id = await service.approve_and_submit(app_record.user_id, app_record.id)
        assert run_id.startswith("sub_")
        
        # Verify status
        await db.refresh(app_record)
        assert app_record.status == ApplicationStatus.APPLIED
        
        # Verify run
        run = await db.get(ApplicationRun, run_id)
        assert run.status == "completed"
        assert run.artifacts is not None
        assert "pre_screenshot" in run.artifacts
        assert "post_screenshot" in run.artifacts
        
        print("\nSUCCESS! Application is APPLIED.")
