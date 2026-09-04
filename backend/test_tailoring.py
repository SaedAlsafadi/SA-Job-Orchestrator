import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_factory
from app.services.tailoring import start_tailoring_session
from app.core.llm.factory import build_llm_router_for_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        # Get first user
        user = (await db.execute(select(User))).scalars().first()
        if not user:
            print("No user found")
            return
            
        # Get a job and resume
        job = (await db.execute(select(Job).where(Job.user_id == user.id))).scalars().first()
        resume = (await db.execute(select(Resume).where(Resume.user_id == user.id))).scalars().first()
        
        if not job or not resume:
            print("Job or Resume missing")
            return
            
        print(f"Running tailoring for Job {job.title} and Resume {resume.name}")
        
        router = await build_llm_router_for_user(db, user.id)
        session = await start_tailoring_session(
            db=db,
            user_id=user.id,
            job_id=job.id,
            base_resume_id=resume.id,
            router=router
        )
        
        print(f"Session status: {session.status}")
        
        # Refresh and get changes
        await db.refresh(session, ["changes"])
        print(f"Generated {len(session.changes)} changes:")
        
        for c in session.changes:
            print(f"\nChange {c.change_type} on {c.target_reference}")
            print(f"Original: {c.original_text}")
            print(f"Proposed: {c.proposed_text}")
            print(f"Reason: {c.reason}")
            print(f"Review: {c.review_severity} ({c.review_reason})")

if __name__ == "__main__":
    asyncio.run(main())


