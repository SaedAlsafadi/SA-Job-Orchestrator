"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

_settings = get_settings()

if _settings.database_url.startswith("sqlite"):
    import os
    db_path = _settings.database_url.split("///")[-1]
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

engine = create_async_engine(
    _settings.database_url,
    # SQL bind values can contain full CVs, cover letters, and other personal data.
    # Keep engine echo opt-in even in development.
    echo=_settings.database_echo,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session with automatic cleanup.

    Usage as a FastAPI dependency:
        async def my_route(db: AsyncSession = Depends(get_db)): ...
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
