import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine, async_sessionmaker
from app.services.discovery_service import DiscoveryService
from app.core.connectors.workable_source import WorkableJobSource

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def run():
    async with SessionLocal() as db:
        service = DiscoveryService(db)
        try:
            jobs = await service.discover_and_store('f9305c63796d4430bcdb178025ea6d64', 'https://jobs.workable.com/en/view/ww7scbfrJsQ5jU9qjNLada/document-controller-in-riyadh-at-hanmiglobal-saudi')
            print(f'Found {len(jobs)} jobs')
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(run())
