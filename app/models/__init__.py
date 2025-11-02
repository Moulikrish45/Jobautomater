"""Data models package for job application automation platform."""

from .user import User, JobPreferences, PersonalInfo, Experience, Education, WorkType
from .job import Job, JobPortal, JobStatus, JobType, ExperienceLevel, SalaryInfo, CompanyInfo, JobLocation
from .application import Application, ApplicationStatus, ApplicationOutcome, ApplicationAttempt, SubmissionData
from .resume import Resume, ResumeType, ResumeFormat, OptimizationMetadata, ResumeSection, ResumeContent, FileInfo

# List of all document models for Beanie initialization
__all__ = [
    # Document models
    "User",
    "Job", 
    "Application",
    "Resume",
    
    # User related models
    "JobPreferences",
    "PersonalInfo", 
    "Experience",
    "Education",
    "WorkType",
    
    # Job related models
    "JobPortal",
    "JobStatus", 
    "JobType",
    "ExperienceLevel",
    "SalaryInfo",
    "CompanyInfo",
    "JobLocation",
    
    # Application related models
    "ApplicationStatus",
    "ApplicationOutcome", 
    "ApplicationAttempt",
    "SubmissionData",
    
    # Resume related models
    "ResumeType",
    "ResumeFormat",
    "OptimizationMetadata",
    "ResumeSection", 
    "ResumeContent",
    "FileInfo"
]

# Document models for Beanie ODM initialization
DOCUMENT_MODELS = [User, Job, Application, Resume]