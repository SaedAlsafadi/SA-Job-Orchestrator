import asyncio
from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.job import Job

async def main():
    async with async_session_factory() as session:
        jobs = (await session.execute(select(Job).where(Job.platform.in_(['workable', 'greenhouse', 'lever'])))).scalars().all()
        for j in jobs:
            print(f"[{j.platform}] {j.title} at {j.company} - {j.url}")

if __name__ == '__main__':
    asyncio.run(main())
