import asyncio
from app.db.session import async_session_factory
from app.models.monitoring import MonitoringSchedule
from app.models.user import User
from sqlalchemy import select

async def seed():
    async with async_session_factory() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        
        if not user:
            print("No users found. Please create a user first.")
            return

        schedules = [
            MonitoringSchedule(
                user_id=user.id,
                platform="workable",
                source="https://jobs.workable.com/search?query=software&remote=true",
                interval_minutes=15,
                match_threshold=80.0,
                max_preparations_per_cycle=1
            ),
            MonitoringSchedule(
                user_id=user.id,
                platform="greenhouse",
                source="https://boards.greenhouse.io/openai",
                interval_minutes=15,
                match_threshold=80.0,
                max_preparations_per_cycle=1
            ),
            MonitoringSchedule(
                user_id=user.id,
                platform="lever",
                source="https://jobs.lever.co/anthropic",
                interval_minutes=15,
                match_threshold=80.0,
                max_preparations_per_cycle=1
            )
        ]
        
        session.add_all(schedules)
        await session.commit()
        print("Schedules seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed())
