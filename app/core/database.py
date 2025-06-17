from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logger import logger

engine = create_async_engine(
    url=settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

class Base(AsyncAttrs, DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession | Any, Any]:
    async with AsyncSessionLocal() as session:
        logger.debug("Database session opened")
        try:
            yield session
        finally:
            logger.debug("Database session closed")