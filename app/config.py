"""Configuration settings for the Job Application Automation Platform."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    app_name: str = "Job Application Automation Platform"
    debug: bool = False
    
    # Database settings
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "job_automation"
    
    # Redis settings
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery settings
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # Security settings
    secret_key: str = "your-secret-key-change-in-production"
    
    # Gemini AI settings
    gemini_api_key: str = "AIzaSyBX-Ztg2I6C5zBrrHxRkCatpAiF2P8JDBE"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()