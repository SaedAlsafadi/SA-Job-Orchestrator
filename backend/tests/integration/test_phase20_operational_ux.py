"""Phase 20A.3 deterministic operational UX API coverage."""

from app.models.application import Application
from app.models.job import Job
from app.models.resume import Resume
from app.models.tailoring import CVTailoringSession
from tests.conftest import TEST_USER_ID


async def _job(db, suffix: str = "1", score: float | None = None) -> Job:
    row = Job(
        user_id=TEST_USER_ID, platform="linkedin", platform_job_id=f"phase20-{suffix}",
        title=f"Phase 20 role {suffix}", company="Example", location="Remote",
        url="https://example.com/job", description="Role", status="ready", match_score=score,
        raw_data={"recommendation": "tailor"} if score is not None else {},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def test_jobs_payload_normalizes_legacy_score_once(client, db_session, current_user):
    await _job(db_session, score=47)
    response = await client.get("/api/v1/jobs/")
    assert response.status_code == 200
    assert response.json()["items"][0]["match_score"] == 0.47


async def test_dashboard_dismissal_persists_each_material_fingerprint(client, current_user):
    payload = {"entity_type": "application", "entity_id": "a" * 32, "fingerprint": "queued:v1"}
    assert (await client.post("/api/v1/dashboard/dismissals", json=payload)).status_code == 201
    assert (await client.post("/api/v1/dashboard/dismissals", json=payload)).status_code == 201
    changed = {**payload, "fingerprint": "failed:v2"}
    assert (await client.post("/api/v1/dashboard/dismissals", json=changed)).status_code == 201
    items = (await client.get("/api/v1/dashboard/dismissals")).json()["items"]
    assert {item["fingerprint"] for item in items} == {"queued:v1", "failed:v2"}


async def test_referenced_resume_archives_without_breaking_application(client, db_session, current_user):
    job = await _job(db_session, "archive")
    resume = Resume(user_id=TEST_USER_ID, name="Referenced", type="base", template_id="modern", content_text="Full content")
    db_session.add(resume)
    await db_session.flush()
    application = Application(user_id=TEST_USER_ID, job_id=job.id, resume_id=resume.id, status="queued", apply_mode="review")
    db_session.add(application)
    await db_session.commit()
    response = await client.post(f"/api/v1/resumes/{resume.id}/archive")
    assert response.status_code == 200
    assert response.json()["archived_at"] is not None
    active = (await client.get("/api/v1/resumes/")).json()["items"]
    assert all(item["id"] != resume.id for item in active)
    await db_session.refresh(application)
    assert application.resume_id == resume.id


async def test_tailored_resume_resolves_existing_revision_session(client, db_session, current_user):
    job = await _job(db_session, "revise", score=.51)
    base = Resume(user_id=TEST_USER_ID, name="Base", type="base", template_id="modern", content_text="Original")
    db_session.add(base)
    await db_session.flush()
    tailored = Resume(user_id=TEST_USER_ID, name="Tailored", type="tailored", template_id="modern", base_resume_id=base.id, job_id=job.id, content_text="Draft")
    db_session.add(tailored)
    await db_session.flush()
    session = CVTailoringSession(user_id=TEST_USER_ID, job_id=job.id, base_resume_id=base.id, status="verified", final_resume_id=tailored.id)
    db_session.add(session)
    await db_session.commit()
    response = await client.get(f"/api/v1/tailoring/resume/{tailored.id}")
    assert response.status_code == 200
    assert response.json()["id"] == session.id


async def test_legacy_tailored_resume_opens_model_free_revision_session(client, db_session, current_user):
    job = await _job(db_session, "legacy-revise", score=.47)
    base = Resume(user_id=TEST_USER_ID, name="Base", type="base", template_id="modern", content_text="Original")
    db_session.add(base)
    await db_session.flush()
    tailored = Resume(
        user_id=TEST_USER_ID,
        name="Legacy tailored",
        type="tailored",
        template_id="modern",
        base_resume_id=base.id,
        job_id=job.id,
        content_text="Previously generated content",
    )
    db_session.add(tailored)
    await db_session.commit()

    response = await client.post(f"/api/v1/tailoring/resume/{tailored.id}/revision")
    assert response.status_code == 200
    body = response.json()
    assert body["base_resume_id"] == tailored.id
    assert body["job_id"] == job.id
    assert body["status"] == "reviewing"
    assert body["changes"] == []

    # Repeated clicks reopen the same active draft rather than duplicating it.
    again = await client.post(f"/api/v1/tailoring/resume/{tailored.id}/revision")
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]
