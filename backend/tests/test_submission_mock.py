import pytest
from app.models.application import Application, ApplicationRun
from app.models.job import Job
from app.models.enums import ApplicationStatus
from app.services.submission_service import SubmissionService
from app.core.connectors.workable_source import WorkableJobSource
import os

pytestmark = pytest.mark.asyncio

async def test_duplicate_approval_rejected(db_session):
    # Setup mock Job and Application
    job = Job(id="j1", user_id="testuser0000000000000000000000aa", title="test", company="test", platform="workable", platform_job_id="w1", url="https://apply.workable.com/test")
    app = Application(id="a1", user_id="testuser0000000000000000000000aa", job_id="j1", status=ApplicationStatus.SUBMITTING)
    db_session.add(job)
    db_session.add(app)
    await db_session.commit()
    
    svc = SubmissionService(db_session)
    
    # Should raise error because it is already submitting
    with pytest.raises(ValueError, match="already in non-submittable state"):
        await svc.approve_and_submit("testuser0000000000000000000000aa", "a1")

async def test_capability_false_rejected(db_session):
    job = Job(id="j2", user_id="testuser0000000000000000000000aa", title="test", company="test", platform="greenhouse", platform_job_id="g1", url="https://boards.greenhouse.io/test")
    app = Application(id="a2", user_id="testuser0000000000000000000000aa", job_id="j2", status=ApplicationStatus.WAITING_FOR_REVIEW)
    db_session.add(job)
    db_session.add(app)
    await db_session.commit()
    
    svc = SubmissionService(db_session)
    
    # Greenhouse has submission=False
    with pytest.raises(ValueError, match="reports submission=False"):
        await svc.approve_and_submit("testuser0000000000000000000000aa", "a2")

async def test_submission_blocked_on_stale_state(db_session):
    job = Job(id="j3", user_id="testuser0000000000000000000000aa", title="test", company="test", platform="workable", platform_job_id="w2", url="https://apply.workable.com/test")
    app = Application(id="a3", user_id="testuser0000000000000000000000aa", job_id="j3", status=ApplicationStatus.WAITING_FOR_REVIEW)
    db_session.add(job)
    db_session.add(app)
    await db_session.commit()
    
    svc = SubmissionService(db_session)
    
    # Missing prep_run with state_data
    run_id = await svc.approve_and_submit("testuser0000000000000000000000aa", "a3")
    
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.SUBMISSION_BLOCKED
    
    # Check the run
    run = await db_session.get(ApplicationRun, run_id)
    assert run.status == "failed"
    assert "Stale or missing preparation state" in run.error

async def test_unresolved_high_risk_question(db_session):
    job = Job(id="j4", user_id="testuser0000000000000000000000aa", title="test", company="test", platform="workable", platform_job_id="w4", url="https://apply.workable.com/test")
    app = Application(id="a4", user_id="testuser0000000000000000000000aa", job_id="j4", status=ApplicationStatus.WAITING_FOR_REVIEW)
    run = ApplicationRun(
        id="prep_run_4",
        user_id="testuser0000000000000000000000aa",
        application_id="a4",
        status="completed",
        state_data={"questions": [{"question_id": "q1", "label": "Dangerous?", "requires_human": True}]}
    )
    db_session.add_all([job, app, run])
    await db_session.commit()
    
    svc = SubmissionService(db_session)
    run_id = await svc.approve_and_submit("testuser0000000000000000000000aa", "a4")
    
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.SUBMISSION_BLOCKED
    db_run = await db_session.get(ApplicationRun, run_id)
    assert "Unresolved high-risk question remains" in db_run.error

