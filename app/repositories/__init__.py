"""Repository pattern implementation for data access layer."""

from .base import BaseRepository
from .user_repository import UserRepository
# Temporarily commenting out other repositories to fix ObjectId issues
# from .job_repository import JobRepository
# from .application_repository import ApplicationRepository
# from .resume_repository import ResumeRepository

__all__ = [
    "BaseRepository",
    "UserRepository"
    # Temporarily only UserRepository
]