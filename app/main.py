import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logger import logger
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api.v1.api import api_router
from app.models import admin, curator, exam, group, mark, student, telegram
from app.utils.bot import main as run_bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENVIRONMENT} environment")
    logger.debug(f"Database URL: {settings.DATABASE_URL}")
    logger.debug(f"Secret Key: {'*' * len(settings.SECRET_KEY)} (hidden)")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.success("База данных успешно инициализирована!")
    except Exception as e:
        logger.critical(f"Ошибка инициализации базы данных: {e}")
        raise

    bot_task = asyncio.create_task(run_bot())
    logger.info("Telegram-бот запущен")

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}")
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        logger.info("Бот остановлен корректно")
    await engine.dispose()
    logger.debug("База данных ликвидирована")

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0", lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")