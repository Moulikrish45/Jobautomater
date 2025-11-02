"""Resume model for storing and managing resume versions."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, validator


class ResumeType(str, Enum):
    """Resume type classification."""
    ORIGINAL = "original"
    OPTIMIZED = "optimized"
    TEMPLATE = "template"


class ResumeFormat(str, Enum):
    """Resume file format."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class OptimizationMetadata(BaseModel):
    """Metadata about resume optimization process."""
    job_id: PydanticObjectId = Field(..., description="Job this resume was optimized for")
    keywords_added: List[str] = Field(default_factory=list, description="Keywords added during optimization")
    keywords_emphasized: List[str] = Field(default_factory=list, description="Existing keywords that were emphasized")
    sections_modified: List[str] = Field(default_factory=list, description="Resume sections that were modified")
    optimization_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Quality score of optimization")
    ai_model_used: Optional[str] = Field(None, description="AI model used for optimization")
    optimization_prompt: Optional[str] = Field(None, max_length=2000, description="Prompt used for AI optimization")
    processing_time_seconds: Optional[float] = Field(None, ge=0.0, description="Time taken for optimization")
    
    @validator('keywords_added', 'keywords_emphasized')
    def validate_keywords(cls, v):
        """Validate keywords lists."""
        if len(v) > 50:
            raise ValueError('Maximum 50 keywords allowed')
        return [keyword.strip().lower() for keyword in v if keyword.strip()]
    
    @validator('sections_modified')
    def validate_sections_modified(cls, v):
        """Validate sections modified list."""
        valid_sections = ['summary', 'experience', 'skills', 'education', 'projects', 'certifications']
        for section in v:
            if section.lower() not in valid_sections:
                raise ValueError(f'Invalid section: {section}. Must be one of {valid_sections}')
        return [section.lower() for section in v]


class ResumeSection(BaseModel):
    """Individual resume section content."""
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    order: int = Field(..., ge=0, description="Display order of section")
    is_visible: bool = Field(default=True, description="Whether section is visible in resume")


class ResumeContent(BaseModel):
    """Structured resume content."""
    sections: List[ResumeSection] = Field(..., min_items=1, description="Resume sections")
    formatting: Dict[str, Any] = Field(default_factory=dict, description="Formatting preferences")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('sections')
    def validate_sections(cls, v):
        """Validate resume sections."""
        if len(v) > 20:
            raise ValueError('Maximum 20 resume sections allowed')
        
        # Check for duplicate section titles
        titles = [section.title.lower() for section in v]
        if len(titles) != len(set(titles)):
            raise ValueError('Duplicate section titles not allowed')
        
        # Validate order numbers are unique
        orders = [section.order for section in v]
        if len(orders) != len(set(orders)):
            raise ValueError('Section order numbers must be unique')
        
        return v


class FileInfo(BaseModel):
    """Resume file information."""
    filename: str = Field(..., min_length=1, max_length=255)
    file_path: str = Field(..., min_length=1, max_length=500)
    file_size_bytes: int = Field(..., ge=0)
    format: ResumeFormat = Field(...)
    checksum: Optional[str] = Field(None, description="File checksum for integrity verification")
    
    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename format."""
        if not v.endswith(('.pdf', '.docx', '.txt')):
            raise ValueError('Filename must end with .pdf, .docx, or .txt')
        return v


class Resume(Document):
    """Resume document model."""
    
    # References
    user_id: PydanticObjectId = Field(..., description="User who owns this resume")
    job_id: Optional[PydanticObjectId] = Field(None, description="Job this resume was optimized for (if applicable)")
    
    # Resume classification
    type: ResumeType = Field(..., description="Type of resume")
    version: int = Field(default=1, ge=1, description="Version number for this resume")
    
    # Content
    content: ResumeContent = Field(..., description="Structured resume content")
    file_info: Optional[FileInfo] = Field(None, description="File information if resume is stored as file")
    
    # Optimization data
    optimization_metadata: Optional[OptimizationMetadata] = Field(None, description="Optimization details")
    parent_resume_id: Optional[PydanticObjectId] = Field(None, description="Original resume this was derived from")
    
    # Status and metadata
    is_active: bool = Field(default=True, description="Whether resume is active/current")
    is_default: bool = Field(default=False, description="Whether this is the default resume for user")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = Field(None, description="When resume was last used for application")
    
    # Additional metadata
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    notes: Optional[str] = Field(None, max_length=1000, description="User notes about this resume")
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags list."""
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return [tag.strip().lower() for tag in v if tag.strip()]
    
    @validator('version')
    def validate_version(cls, v):
        """Validate version number."""
        if v > 100:
            raise ValueError('Version number cannot exceed 100')
        return v
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
    
    def mark_as_used(self):
        """Mark resume as recently used."""
        self.last_used_at = datetime.utcnow()
        self.update_timestamp()
    
    def add_tag(self, tag: str):
        """Add a tag to the resume."""
        tag = tag.strip().lower()
        if tag and tag not in self.tags:
            if len(self.tags) >= 10:
                raise ValueError('Maximum 10 tags allowed')
            self.tags.append(tag)
            self.update_timestamp()
    
    def remove_tag(self, tag: str):
        """Remove a tag from the resume."""
        tag = tag.strip().lower()
        if tag in self.tags:
            self.tags.remove(tag)
            self.update_timestamp()
    
    def get_section_by_title(self, title: str) -> Optional[ResumeSection]:
        """Get resume section by title."""
        for section in self.content.sections:
            if section.title.lower() == title.lower():
                return section
        return None
    
    def update_section_content(self, title: str, new_content: str):
        """Update content of a specific section."""
        section = self.get_section_by_title(title)
        if section:
            section.content = new_content
            self.update_timestamp()
        else:
            raise ValueError(f'Section "{title}" not found')
    
    @property
    def is_optimized(self) -> bool:
        """Check if this is an optimized resume."""
        return self.type == ResumeType.OPTIMIZED and self.optimization_metadata is not None
    
    @property
    def word_count(self) -> int:
        """Get approximate word count of resume content."""
        total_words = 0
        for section in self.content.sections:
            total_words += len(section.content.split())
        return total_words
    
    class Settings:
        name = "resumes"
        indexes = [
            "user_id",
            "job_id",
            "type",
            "is_active",
            "is_default",
            "created_at",
            "last_used_at",
            [("user_id", 1), ("type", 1)],
            [("user_id", 1), ("is_active", 1)],
            [("user_id", 1), ("is_default", 1)],
            [("user_id", 1), ("last_used_at", -1)]
        ]