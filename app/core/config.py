from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Roy Student Backend"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str
    SECRET_KEY: str = "roy-student-backend"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ENVIRONMENT: str = "development"
    LOG_DIR: str = "logs"
    ADMIN_KEY: str
    CURATOR_KEY: str
    BOT_TOKEN: str

    class Config:
        case_sensitive = True


settings = Settings()
