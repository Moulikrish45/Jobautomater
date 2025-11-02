"""PDF generation service for resume creation using ReportLab."""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import hashlib
import json

import aiofiles
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import black, darkblue, gray
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from app.config import settings


class PDFGenerationError(Exception):
    """Base exception for PDF generation errors."""
    pass


class FileStorageError(Exception):
    """Exception for file storage operations."""
    pass


class ResumeTemplate:
    """Base class for resume PDF templates."""
    
    def __init__(self, page_size=letter, template_style="professional"):
        """Initialize template with page size and style.
        
        Args:
            page_size: Page size tuple (width, height)
            template_style: Template style (professional, modern, minimal)
        """
        self.page_size = page_size
        self.template_style = template_style
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles for resume based on template style."""
        # Style variations based on template
        if self.template_style == "modern":
            header_color = black
            section_color = gray
            header_size = 20
        elif self.template_style == "minimal":
            header_color = black
            section_color = black
            header_size = 16
        else:  # professional (default)
            header_color = darkblue
            section_color = darkblue
            header_size = 18
        
        # Header style for name
        self.styles.add(ParagraphStyle(
            name='ResumeHeader',
            parent=self.styles['Heading1'],
            fontSize=header_size,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=header_color,
            fontName='Helvetica-Bold'
        ))
        
        # Contact info style
        self.styles.add(ParagraphStyle(
            name='ContactInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=12
        ))
        
        # Section header style
        if self.template_style == "minimal":
            # Minimal style - no borders
            self.styles.add(ParagraphStyle(
                name='SectionHeader',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceBefore=12,
                spaceAfter=6,
                textColor=section_color,
                fontName='Helvetica-Bold'
            ))
        else:
            # Professional and modern styles with borders
            self.styles.add(ParagraphStyle(
                name='SectionHeader',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceBefore=12,
                spaceAfter=6,
                textColor=section_color,
                borderWidth=1,
                borderColor=section_color,
                borderPadding=2,
                fontName='Helvetica-Bold'
            ))
        
        # Job title style
        self.styles.add(ParagraphStyle(
            name='JobTitle',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceBefore=6,
            spaceAfter=2,
            fontName='Helvetica-Bold'
        ))
        
        # Company and date style
        self.styles.add(ParagraphStyle(
            name='CompanyDate',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            textColor=gray,
            fontName='Helvetica-Oblique'
        ))
        
        # Bullet point style
        self.styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=20,
            bulletIndent=10,
            spaceAfter=2
        ))
        
        # Skills category style
        self.styles.add(ParagraphStyle(
            name='SkillsCategory',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceBefore=4,
            spaceAfter=2,
            fontName='Helvetica-Bold'
        ))
    
    def generate_pdf(
        self,
        resume_content: Dict[str, Any],
        output_path: str
    ) -> None:
        """Generate PDF resume from content dictionary.
        
        Args:
            resume_content: Resume content dictionary
            output_path: Output file path
            
        Raises:
            PDFGenerationError: If PDF generation fails
        """
        try:
            # Create document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )
            
            # Build content
            story = []
            
            # Add header (name and contact info)
            self._add_header(story, resume_content)
            
            # Add summary/objective
            if resume_content.get("summary"):
                self._add_summary(story, resume_content["summary"])
            
            # Add experience
            if resume_content.get("experience"):
                self._add_experience(story, resume_content["experience"])
            
            # Add skills
            if resume_content.get("skills"):
                self._add_skills(story, resume_content["skills"])
            
            # Add education
            if resume_content.get("education"):
                self._add_education(story, resume_content["education"])
            
            # Add certifications if present
            if resume_content.get("certifications"):
                self._add_certifications(story, resume_content["certifications"])
            
            # Add projects if present
            if resume_content.get("projects"):
                self._add_projects(story, resume_content["projects"])
            
            # Build PDF
            doc.build(story)
            
        except Exception as e:
            raise PDFGenerationError(f"PDF generation failed: {e}")
    
    def _add_header(self, story: List, resume_content: Dict[str, Any]) -> None:
        """Add header section with name and contact info."""
        # Name
        name = resume_content.get("personal_info", {}).get("name", "")
        if name:
            story.append(Paragraph(name, self.styles['ResumeHeader']))
        
        # Contact information
        contact_parts = []
        personal_info = resume_content.get("personal_info", {})
        
        if personal_info.get("email"):
            contact_parts.append(personal_info["email"])
        if personal_info.get("phone"):
            contact_parts.append(personal_info["phone"])
        if personal_info.get("location"):
            contact_parts.append(personal_info["location"])
        if personal_info.get("linkedin"):
            contact_parts.append(f"LinkedIn: {personal_info['linkedin']}")
        
        if contact_parts:
            contact_text = " | ".join(contact_parts)
            story.append(Paragraph(contact_text, self.styles['ContactInfo']))
        
        story.append(Spacer(1, 12))
    
    def _add_summary(self, story: List, summary: str) -> None:
        """Add professional summary section."""
        story.append(Paragraph("PROFESSIONAL SUMMARY", self.styles['SectionHeader']))
        story.append(Paragraph(summary, self.styles['Normal']))
        story.append(Spacer(1, 12))
    
    def _add_experience(self, story: List, experience: List[Dict[str, Any]]) -> None:
        """Add work experience section."""
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", self.styles['SectionHeader']))
        
        for job in experience:
            # Job title
            title = job.get("title", "")
            if title:
                story.append(Paragraph(title, self.styles['JobTitle']))
            
            # Company and dates
            company_date_parts = []
            if job.get("company"):
                company_date_parts.append(job["company"])
            if job.get("duration"):
                company_date_parts.append(job["duration"])
            
            if company_date_parts:
                company_date_text = " | ".join(company_date_parts)
                story.append(Paragraph(company_date_text, self.styles['CompanyDate']))
            
            # Job description/responsibilities
            description = job.get("description", "")
            if description:
                # Handle bullet points
                if isinstance(description, str):
                    # Split by bullet points or newlines
                    if "•" in description or "-" in description:
                        lines = description.split("\n")
                        for line in lines:
                            line = line.strip()
                            if line:
                                # Remove existing bullet characters
                                line = line.lstrip("•-").strip()
                                story.append(Paragraph(f"• {line}", self.styles['BulletPoint']))
                    else:
                        story.append(Paragraph(description, self.styles['Normal']))
                elif isinstance(description, list):
                    for item in description:
                        story.append(Paragraph(f"• {item}", self.styles['BulletPoint']))
            
            story.append(Spacer(1, 8))
        
        story.append(Spacer(1, 12))
    
    def _add_skills(self, story: List, skills: Any) -> None:
        """Add skills section."""
        story.append(Paragraph("TECHNICAL SKILLS", self.styles['SectionHeader']))
        
        if isinstance(skills, list):
            # Group skills or display as comma-separated
            skills_text = ", ".join(skills)
            story.append(Paragraph(skills_text, self.styles['Normal']))
        elif isinstance(skills, dict):
            # Categorized skills
            for category, skill_list in skills.items():
                if isinstance(skill_list, list):
                    category_text = f"<b>{category.title()}:</b> {', '.join(skill_list)}"
                    story.append(Paragraph(category_text, self.styles['Normal']))
        elif isinstance(skills, str):
            story.append(Paragraph(skills, self.styles['Normal']))
        
        story.append(Spacer(1, 12))
    
    def _add_education(self, story: List, education: List[Dict[str, Any]]) -> None:
        """Add education section."""
        story.append(Paragraph("EDUCATION", self.styles['SectionHeader']))
        
        for edu in education:
            # Degree and institution
            degree_parts = []
            if edu.get("degree"):
                degree_parts.append(edu["degree"])
            if edu.get("institution"):
                degree_parts.append(edu["institution"])
            
            if degree_parts:
                degree_text = " | ".join(degree_parts)
                story.append(Paragraph(degree_text, self.styles['JobTitle']))
            
            # Year and additional info
            if edu.get("year"):
                story.append(Paragraph(str(edu["year"]), self.styles['CompanyDate']))
            
            if edu.get("gpa"):
                story.append(Paragraph(f"GPA: {edu['gpa']}", self.styles['Normal']))
            
            story.append(Spacer(1, 6))
        
        story.append(Spacer(1, 12))
    
    def _add_certifications(self, story: List, certifications: List[Dict[str, Any]]) -> None:
        """Add certifications section."""
        story.append(Paragraph("CERTIFICATIONS", self.styles['SectionHeader']))
        
        for cert in certifications:
            cert_parts = []
            if cert.get("name"):
                cert_parts.append(cert["name"])
            if cert.get("issuer"):
                cert_parts.append(cert["issuer"])
            if cert.get("year"):
                cert_parts.append(str(cert["year"]))
            
            if cert_parts:
                cert_text = " | ".join(cert_parts)
                story.append(Paragraph(f"• {cert_text}", self.styles['BulletPoint']))
        
        story.append(Spacer(1, 12))
    
    def _add_projects(self, story: List, projects: List[Dict[str, Any]]) -> None:
        """Add projects section."""
        story.append(Paragraph("PROJECTS", self.styles['SectionHeader']))
        
        for project in projects:
            # Project name
            if project.get("name"):
                story.append(Paragraph(project["name"], self.styles['JobTitle']))
            
            # Technologies and date
            tech_date_parts = []
            if project.get("technologies"):
                if isinstance(project["technologies"], list):
                    tech_date_parts.append(", ".join(project["technologies"]))
                else:
                    tech_date_parts.append(str(project["technologies"]))
            if project.get("date"):
                tech_date_parts.append(str(project["date"]))
            
            if tech_date_parts:
                story.append(Paragraph(" | ".join(tech_date_parts), self.styles['CompanyDate']))
            
            # Description
            if project.get("description"):
                story.append(Paragraph(project["description"], self.styles['Normal']))
            
            story.append(Spacer(1, 6))
        
        story.append(Spacer(1, 12))


class FileManager:
    """Async file management for resume storage with enhanced metadata tracking."""
    
    def __init__(self, base_path: str = None):
        """Initialize file manager.
        
        Args:
            base_path: Base directory for file storage
        """
        self.base_path = Path(base_path or settings.resume_storage_path)
        self.logger = logging.getLogger(__name__)
        self._file_metadata_cache = {}
    
    async def ensure_directory(self, directory: Path) -> None:
        """Ensure directory exists, create if necessary.
        
        Args:
            directory: Directory path to ensure
            
        Raises:
            FileStorageError: If directory creation fails
        """
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileStorageError(f"Failed to create directory {directory}: {e}")
    
    async def generate_file_path(
        self,
        user_id: str,
        job_id: Optional[str] = None,
        resume_type: str = "original",
        extension: str = "pdf"
    ) -> Path:
        """Generate file path for resume storage.
        
        Args:
            user_id: User ID
            job_id: Job ID (for optimized resumes)
            resume_type: Resume type (original, optimized)
            extension: File extension
            
        Returns:
            Generated file path
        """
        # Create user directory
        user_dir = self.base_path / user_id
        await self.ensure_directory(user_dir)
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if job_id and resume_type == "optimized":
            filename = f"resume_optimized_{job_id}_{timestamp}.{extension}"
        else:
            filename = f"resume_{resume_type}_{timestamp}.{extension}"
        
        return user_dir / filename
    
    async def save_file(
        self,
        content: bytes,
        file_path: Path,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Save file content to disk with enhanced metadata tracking.
        
        Args:
            content: File content as bytes
            file_path: Target file path
            metadata: Additional metadata to store
            
        Returns:
            File metadata
            
        Raises:
            FileStorageError: If file save fails
        """
        try:
            # Ensure parent directory exists
            await self.ensure_directory(file_path.parent)
            
            # Write file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            # Calculate file hash
            file_hash = hashlib.sha256(content).hexdigest()
            
            # Get file stats
            stat = file_path.stat()
            
            # Create comprehensive metadata
            file_metadata = {
                "path": str(file_path),
                "filename": file_path.name,
                "size": stat.st_size,
                "hash": file_hash,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "content_type": "application/pdf",
                "version": 1
            }
            
            # Add custom metadata
            if metadata:
                file_metadata.update(metadata)
            
            # Cache metadata
            self._file_metadata_cache[str(file_path)] = file_metadata
            
            # Save metadata to JSON file
            await self._save_metadata_file(file_path, file_metadata)
            
            return file_metadata
            
        except Exception as e:
            raise FileStorageError(f"Failed to save file {file_path}: {e}")
    
    async def _save_metadata_file(self, file_path: Path, metadata: Dict[str, Any]) -> None:
        """Save metadata to JSON file alongside the main file.
        
        Args:
            file_path: Main file path
            metadata: Metadata to save
        """
        try:
            metadata_path = file_path.with_suffix('.json')
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
        except Exception as e:
            self.logger.warning(f"Failed to save metadata file for {file_path}: {e}")
    
    async def _load_metadata_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load metadata from JSON file.
        
        Args:
            file_path: Main file path
            
        Returns:
            Loaded metadata or None
        """
        try:
            metadata_path = file_path.with_suffix('.json')
            if metadata_path.exists():
                async with aiofiles.open(metadata_path, 'r') as f:
                    content = await f.read()
                    return json.loads(content)
        except Exception as e:
            self.logger.warning(f"Failed to load metadata file for {file_path}: {e}")
        return None
    
    async def read_file(self, file_path: Path) -> bytes:
        """Read file content from disk.
        
        Args:
            file_path: File path to read
            
        Returns:
            File content as bytes
            
        Raises:
            FileStorageError: If file read fails
        """
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except Exception as e:
            raise FileStorageError(f"Failed to read file {file_path}: {e}")
    
    async def delete_file(self, file_path: Path) -> bool:
        """Delete file from disk.
        
        Args:
            file_path: File path to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            FileStorageError: If file deletion fails
        """
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            raise FileStorageError(f"Failed to delete file {file_path}: {e}")
    
    async def get_file_metadata(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Get comprehensive file metadata.
        
        Args:
            file_path: File path
            
        Returns:
            File metadata or None if file doesn't exist
        """
        try:
            if not file_path.exists():
                return None
            
            # Check cache first
            cache_key = str(file_path)
            if cache_key in self._file_metadata_cache:
                cached_metadata = self._file_metadata_cache[cache_key]
                # Verify file hasn't changed
                stat = file_path.stat()
                cached_mtime = datetime.fromisoformat(cached_metadata["modified_at"])
                file_mtime = datetime.fromtimestamp(stat.st_mtime)
                
                if abs((file_mtime - cached_mtime).total_seconds()) < 1:
                    return cached_metadata
            
            # Load from metadata file
            stored_metadata = await self._load_metadata_file(file_path)
            if stored_metadata:
                self._file_metadata_cache[cache_key] = stored_metadata
                return stored_metadata
            
            # Fallback to basic file stats
            stat = file_path.stat()
            
            basic_metadata = {
                "path": str(file_path),
                "filename": file_path.name,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "exists": True,
                "content_type": "application/pdf"
            }
            
            return basic_metadata
            
        except Exception as e:
            self.logger.error(f"Failed to get file metadata for {file_path}: {e}")
            return None
    
    async def update_file_metadata(
        self,
        file_path: Path,
        metadata_updates: Dict[str, Any]
    ) -> bool:
        """Update file metadata.
        
        Args:
            file_path: File path
            metadata_updates: Metadata updates to apply
            
        Returns:
            True if updated successfully
        """
        try:
            current_metadata = await self.get_file_metadata(file_path)
            if not current_metadata:
                return False
            
            # Update metadata
            current_metadata.update(metadata_updates)
            current_metadata["modified_at"] = datetime.utcnow().isoformat()
            
            # Save updated metadata
            await self._save_metadata_file(file_path, current_metadata)
            
            # Update cache
            self._file_metadata_cache[str(file_path)] = current_metadata
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update metadata for {file_path}: {e}")
            return False


class PDFService:
    """Enhanced service for PDF generation and file management."""
    
    def __init__(self):
        """Initialize PDF service."""
        self.file_manager = FileManager()
        self.templates = {
            "professional": ResumeTemplate(template_style="professional"),
            "modern": ResumeTemplate(template_style="modern"),
            "minimal": ResumeTemplate(template_style="minimal")
        }
        self.logger = logging.getLogger(__name__)
    
    async def generate_resume_pdf(
        self,
        resume_content: Dict[str, Any],
        user_id: str,
        job_id: Optional[str] = None,
        resume_type: str = "original",
        template_style: str = "professional"
    ) -> Dict[str, Any]:
        """Generate PDF resume and save to storage with enhanced features.
        
        Args:
            resume_content: Resume content dictionary
            user_id: User ID
            job_id: Job ID (for optimized resumes)
            resume_type: Resume type (original, optimized)
            template_style: Template style (professional, modern, minimal)
            
        Returns:
            PDF generation result with file path and metadata
            
        Raises:
            PDFGenerationError: If PDF generation fails
        """
        try:
            # Validate template style
            if template_style not in self.templates:
                template_style = "professional"
                self.logger.warning(f"Invalid template style, using default: {template_style}")
            
            # Generate file path
            file_path = await self.file_manager.generate_file_path(
                user_id=user_id,
                job_id=job_id,
                resume_type=resume_type,
                extension="pdf"
            )
            
            # Generate PDF in memory first (for error handling)
            temp_path = file_path.with_suffix('.tmp')
            
            # Generate PDF using selected template
            template = self.templates[template_style]
            await asyncio.get_event_loop().run_in_executor(
                None, 
                template.generate_pdf, 
                resume_content, 
                str(temp_path)
            )
            
            # Read generated PDF
            pdf_content = await self.file_manager.read_file(temp_path)
            
            # Prepare metadata
            pdf_metadata = {
                "user_id": user_id,
                "job_id": job_id,
                "resume_type": resume_type,
                "template_style": template_style,
                "generated_at": datetime.utcnow().isoformat(),
                "content_hash": hashlib.sha256(json.dumps(resume_content, sort_keys=True).encode()).hexdigest()
            }
            
            # Save to final location with metadata
            file_metadata = await self.file_manager.save_file(
                pdf_content, 
                file_path, 
                pdf_metadata
            )
            
            # Clean up temp file
            await self.file_manager.delete_file(temp_path)
            
            self.logger.info(f"Generated PDF resume: {file_path} (template: {template_style})")
            
            return {
                "success": True,
                "file_path": str(file_path),
                "file_metadata": file_metadata,
                "resume_type": resume_type,
                "template_style": template_style,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"PDF generation failed: {e}")
            # Clean up temp file if it exists
            try:
                if 'temp_path' in locals():
                    await self.file_manager.delete_file(temp_path)
            except:
                pass
            
            raise PDFGenerationError(f"PDF generation failed: {e}")
    
    async def generate_multiple_templates(
        self,
        resume_content: Dict[str, Any],
        user_id: str,
        job_id: Optional[str] = None,
        resume_type: str = "original",
        template_styles: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate PDF resumes using multiple templates.
        
        Args:
            resume_content: Resume content dictionary
            user_id: User ID
            job_id: Job ID (for optimized resumes)
            resume_type: Resume type (original, optimized)
            template_styles: List of template styles to generate
            
        Returns:
            Generation results for all templates
        """
        if not template_styles:
            template_styles = ["professional", "modern", "minimal"]
        
        results = {}
        
        for template_style in template_styles:
            try:
                result = await self.generate_resume_pdf(
                    resume_content=resume_content,
                    user_id=user_id,
                    job_id=job_id,
                    resume_type=resume_type,
                    template_style=template_style
                )
                results[template_style] = result
            except Exception as e:
                self.logger.error(f"Failed to generate {template_style} template: {e}")
                results[template_style] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": True,
            "templates_generated": len([r for r in results.values() if r.get("success")]),
            "results": results
        }
    
    async def get_resume_pdf(self, file_path: str) -> Optional[bytes]:
        """Get resume PDF content.
        
        Args:
            file_path: PDF file path
            
        Returns:
            PDF content as bytes or None if not found
        """
        try:
            path = Path(file_path)
            if path.exists():
                return await self.file_manager.read_file(path)
            return None
        except Exception as e:
            self.logger.error(f"Failed to read PDF {file_path}: {e}")
            return None
    
    async def delete_resume_pdf(self, file_path: str) -> bool:
        """Delete resume PDF file.
        
        Args:
            file_path: PDF file path
            
        Returns:
            True if deleted successfully
        """
        try:
            path = Path(file_path)
            return await self.file_manager.delete_file(path)
        except Exception as e:
            self.logger.error(f"Failed to delete PDF {file_path}: {e}")
            return False
    
    async def list_user_resumes(self, user_id: str) -> List[Dict[str, Any]]:
        """List all resume files for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of resume file metadata
        """
        try:
            user_dir = self.file_manager.base_path / user_id
            
            if not user_dir.exists():
                return []
            
            resumes = []
            for file_path in user_dir.glob("*.pdf"):
                metadata = await self.file_manager.get_file_metadata(file_path)
                if metadata:
                    # Parse filename to extract type and job_id
                    filename = file_path.name
                    if "optimized" in filename:
                        resume_type = "optimized"
                        # Extract job_id from filename if present
                        parts = filename.split("_")
                        job_id = parts[2] if len(parts) > 2 else None
                    else:
                        resume_type = "original"
                        job_id = None
                    
                    metadata.update({
                        "resume_type": resume_type,
                        "job_id": job_id,
                        "filename": filename
                    })
                    resumes.append(metadata)
            
            # Sort by creation date (newest first)
            resumes.sort(key=lambda x: x["created_at"], reverse=True)
            
            return resumes
            
        except Exception as e:
            self.logger.error(f"Failed to list user resumes for {user_id}: {e}")
            return []
    
    async def get_resume_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get analytics for user's resume files.
        
        Args:
            user_id: User ID
            
        Returns:
            Resume analytics data
        """
        try:
            resumes = await self.list_user_resumes(user_id)
            
            analytics = {
                "total_resumes": len(resumes),
                "original_count": 0,
                "optimized_count": 0,
                "template_usage": {},
                "total_size": 0,
                "average_size": 0,
                "latest_resume": None,
                "oldest_resume": None
            }
            
            if not resumes:
                return analytics
            
            # Calculate statistics
            for resume in resumes:
                analytics["total_size"] += resume.get("size", 0)
                
                if resume.get("resume_type") == "original":
                    analytics["original_count"] += 1
                else:
                    analytics["optimized_count"] += 1
                
                # Track template usage
                template_style = resume.get("template_style", "unknown")
                analytics["template_usage"][template_style] = analytics["template_usage"].get(template_style, 0) + 1
            
            analytics["average_size"] = analytics["total_size"] / len(resumes)
            
            # Find latest and oldest
            sorted_resumes = sorted(resumes, key=lambda x: x["created_at"])
            analytics["oldest_resume"] = sorted_resumes[0]
            analytics["latest_resume"] = sorted_resumes[-1]
            
            return analytics
            
        except Exception as e:
            self.logger.error(f"Failed to get resume analytics for {user_id}: {e}")
            return {"error": str(e)}
    
    async def cleanup_user_files(
        self,
        user_id: str,
        keep_count: int = 10,
        cleanup_temp_files: bool = True
    ) -> Dict[str, Any]:
        """Clean up old resume files for a user.
        
        Args:
            user_id: User ID
            keep_count: Number of files to keep
            cleanup_temp_files: Whether to clean up temporary files
            
        Returns:
            Cleanup results
        """
        try:
            user_dir = self.file_manager.base_path / user_id
            
            if not user_dir.exists():
                return {"success": True, "message": "No files to clean up", "deleted_count": 0}
            
            deleted_count = 0
            
            # Clean up temporary files
            if cleanup_temp_files:
                for temp_file in user_dir.glob("*.tmp"):
                    try:
                        await self.file_manager.delete_file(temp_file)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to delete temp file {temp_file}: {e}")
            
            # Get all PDF files
            pdf_files = list(user_dir.glob("*.pdf"))
            
            if len(pdf_files) <= keep_count:
                return {
                    "success": True,
                    "message": f"No cleanup needed. User has {len(pdf_files)} files (limit: {keep_count})",
                    "deleted_count": deleted_count
                }
            
            # Sort by modification time (oldest first)
            pdf_files.sort(key=lambda f: f.stat().st_mtime)
            
            # Delete oldest files
            files_to_delete = pdf_files[:-keep_count]
            
            for file_path in files_to_delete:
                try:
                    # Delete PDF file
                    await self.file_manager.delete_file(file_path)
                    
                    # Delete associated metadata file
                    metadata_file = file_path.with_suffix('.json')
                    if metadata_file.exists():
                        await self.file_manager.delete_file(metadata_file)
                    
                    deleted_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to delete file {file_path}: {e}")
            
            return {
                "success": True,
                "message": f"Cleaned up {deleted_count} files",
                "deleted_count": deleted_count,
                "remaining_files": len(pdf_files) - len(files_to_delete)
            }
            
        except Exception as e:
            self.logger.error(f"File cleanup failed for user {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def validate_resume_content(self, resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resume content before PDF generation.
        
        Args:
            resume_content: Resume content to validate
            
        Returns:
            Validation results
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Check required sections
        required_sections = ["personal_info", "summary", "experience", "skills"]
        for section in required_sections:
            if section not in resume_content:
                validation_result["errors"].append(f"Missing required section: {section}")
                validation_result["valid"] = False
        
        # Validate personal info
        if "personal_info" in resume_content:
            personal_info = resume_content["personal_info"]
            if not personal_info.get("name"):
                validation_result["errors"].append("Name is required in personal_info")
                validation_result["valid"] = False
            
            if not personal_info.get("email"):
                validation_result["warnings"].append("Email is recommended in personal_info")
        
        # Validate experience section
        if "experience" in resume_content:
            experience = resume_content["experience"]
            if isinstance(experience, list):
                for i, job in enumerate(experience):
                    if not isinstance(job, dict):
                        validation_result["errors"].append(f"Experience entry {i+1} must be a dictionary")
                        validation_result["valid"] = False
                        continue
                    
                    if not job.get("title"):
                        validation_result["warnings"].append(f"Experience entry {i+1} missing job title")
                    
                    if not job.get("company"):
                        validation_result["warnings"].append(f"Experience entry {i+1} missing company")
        
        # Validate skills section
        if "skills" in resume_content:
            skills = resume_content["skills"]
            if isinstance(skills, list) and len(skills) < 3:
                validation_result["suggestions"].append("Consider adding more skills (recommended: 5-10)")
            elif isinstance(skills, str) and len(skills.split(",")) < 3:
                validation_result["suggestions"].append("Consider adding more skills (recommended: 5-10)")
        
        return validation_result


# Global service instance
pdf_service = PDFService()