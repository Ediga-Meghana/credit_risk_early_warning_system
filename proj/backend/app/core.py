import os, json, pathlib, datetime as dt
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./riskapp.db"   # MySQL: mysql+pymysql://user:pass@localhost:3306/riskdb
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_MINUTES: int = 60
    ADMIN_EMAIL: str = "admin@riskapp.local"
    ADMIN_PASSWORD: str = "Admin@12345"
    CORS_ORIGINS: str = "http://localhost:5173"
    AI_PROVIDER: str = ""      # "anthropic" | "" (fallback)
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    # Email OTP for public self-service signup (SMTP port 587 with STARTTLS).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    SIGNUP_OTP_TTL_MINUTES: int = 10
    SIGNUP_OTP_RESEND_SECONDS: int = 60
    class Config: env_file = ".env"
settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()
ART = pathlib.Path(__file__).resolve().parent.parent / "ml" / "artifacts"
def now(): return dt.datetime.utcnow()
