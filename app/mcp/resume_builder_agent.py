"""Resume Builder MCP Agent for AI-powered resume optimization."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from app.mcp.base_agent import BaseAgent, AgentError
from app.services.ollama_service import ollama_service, OllamaError
from app.services.nlp_service import nlp_service, ATSOptimizer
from app.services.pdf_service import pdf_service, PDFGenerationError
from app.services.resume_versioning_service import resume_versioning_service, VersionAction
from app.repositories.resume_repository import resume_repository
from app.repositories.job_repository import job_repository
from app.models.resume import Resume, ResumeType, OptimizationMetadata
from app.config import settings


class ResumeBuilderAgent(BaseAgent):
    """MCP Agent for resume optimization and AI-powered content generation."""
    
    def __init__(self):
        """Initialize the Resume Builder Agent."""
        super().__init__(
            name="resume_builder",
            description="AI-powered resume optimization and generation agent"
        )
        self.ollama = ollama_service
        
    async def _initialize(self) -> None:
        """Initialize agent-specific resources."""
        self.logger.info("Initializing Resume Builder Agent")
        
        # Initialize NLP service
        try:
            await nlp_service.initialize()
            self.logger.info("NLP service initialized successfully")
        except Exception as e:
            self.logger.warning(f"NLP service initialization failed: {e}")
        
        # Check Ollama service health
        health = await self.ollama.health_check()
        if health["status"] != "healthy":
            self.logger.warning(f"Ollama service not healthy: {health}")
        else:
            self.logger.info(f"Ollama service healthy with {len(health['available_models'])} models")
        
        # Ensure default model is available
        try:
            await self.ollama.ensure_model_available()
            self.logger.info(f"Default model '{self.ollama.default_model}' is available")
        except Exception as e:
            self.logger.warning(f"Default model not available: {e}")
    
    async def _cleanup(self) -> None:
        """Cleanup agent-specific resources."""
        self.logger.info("Cleaning up Resume Builder Agent")
        # No specific cleanup needed for this agent
    
    async def _execute_task_impl(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute resume building task.
        
        Args:
            task_data: Task parameters containing:
                - action: Task action (optimize_resume, extract_keywords, analyze_resume)
                - user_id: User ID
                - job_id: Job ID (for optimization)
                - resume_id: Resume ID (optional)
                - resume_content: Resume content (optional)
                
        Returns:
            Task execution result
        """
        action = task_data.get("action")
        
        if action == "optimize_resume":
            return await self._optimize_resume_for_job(task_data)
        elif action == "extract_keywords":
            return await self._extract_job_keywords(task_data)
        elif action == "analyze_resume":
            return await self._analyze_resume_content(task_data)
        elif action == "suggest_improvements":
            return await self._suggest_resume_improvements(task_data)
        elif action == "validate_ats":
            return await self._validate_ats_compliance(task_data)
        elif action == "generate_pdf":
            return await self._generate_resume_pdf(task_data)
        elif action == "list_resumes":
            return await self._list_user_resumes(task_data)
        elif action == "get_version_history":
            return await self._get_version_history(task_data)
        elif action == "get_optimization_history":
            return await self._get_optimization_history(task_data)
        else:
            raise AgentError(f"Unknown action: {action}")
    
    async def _optimize_resume_for_job(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize resume for a specific job posting.
        
        Args:
            task_data: Task data with user_id, job_id, and optional resume_id
            
        Returns:
            Optimization result with new resume ID
        """
        user_id = task_data.get("user_id")
        job_id = task_data.get("job_id")
        resume_id = task_data.get("resume_id")
        
        if not user_id or not job_id:
            raise AgentError("user_id and job_id are required for resume optimization")
        
        try:
            # Get job details
            job = await job_repository.get_by_id(job_id)
            if not job:
                raise AgentError(f"Job not found: {job_id}")
            
            # Get original resume
            if resume_id:
                original_resume = await resume_repository.get_by_id(resume_id)
            else:
                # Get user's latest original resume
                original_resume = await resume_repository.get_user_original_resume(user_id)
            
            if not original_resume:
                raise AgentError(f"No original resume found for user: {user_id}")
            
            # Analyze job description and resume for better optimization
            keyword_analysis = nlp_service.calculate_keyword_match_score(
                nlp_service._resume_dict_to_text(original_resume.content),
                job.description
            )
            
            # Apply ATS optimization first
            ats_optimized_content = ATSOptimizer.optimize_formatting(original_resume.content)
            
            # Optimize resume using AI
            optimization_result = await self.ollama.optimize_resume(
                resume_content=ats_optimized_content,
                job_description=job.description
            )
            
            # Calculate optimization score based on keyword matching
            optimization_score = keyword_analysis.get("weighted_match_score", 0.0)
            
            # Generate PDF for optimized resume
            pdf_result = await pdf_service.generate_resume_pdf(
                resume_content=optimization_result["optimized_content"],
                user_id=user_id,
                job_id=job_id,
                resume_type="optimized"
            )
            
            # Create optimized resume record
            optimized_resume = Resume(
                user_id=user_id,
                job_id=job_id,
                type=ResumeType.OPTIMIZED,
                content=optimization_result["optimized_content"],
                file_path=pdf_result["file_path"],
                optimization_metadata=OptimizationMetadata(
                    original_resume_id=str(original_resume.id),
                    keywords_added=optimization_result.get("keywords_added", []),
                    optimization_notes=optimization_result.get("optimization_notes", ""),
                    model_used=optimization_result["optimization_metadata"]["model_used"],
                    optimization_score=optimization_score
                )
            )
            
            # Save optimized resume
            saved_resume = await resume_repository.create(optimized_resume)
            
            # Create version entry
            await resume_versioning_service.create_version(
                resume=saved_resume,
                action=VersionAction.OPTIMIZED,
                parent_version_id=str(original_resume.id),
                metadata={
                    "optimization_score": optimization_score,
                    "keywords_added_count": len(optimization_result.get("keywords_added", [])),
                    "model_used": optimization_result["optimization_metadata"]["model_used"]
                }
            )
            
            self.logger.info(f"Created optimized resume {saved_resume.id} for job {job_id}")
            
            return {
                "success": True,
                "resume_id": str(saved_resume.id),
                "file_path": pdf_result["file_path"],
                "keywords_added": optimization_result.get("keywords_added", []),
                "optimization_notes": optimization_result.get("optimization_notes", ""),
                "optimization_score": optimization_score,
                "created_at": saved_resume.created_at.isoformat()
            }
            
        except OllamaError as e:
            self.logger.error(f"AI optimization failed: {e}")
            raise AgentError(f"Resume optimization failed: {e}")
        except Exception as e:
            self.logger.error(f"Resume optimization error: {e}")
            raise AgentError(f"Resume optimization error: {e}")
    
    async def _extract_job_keywords(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract keywords from job description.
        
        Args:
            task_data: Task data with job_id or job_description
            
        Returns:
            Extracted keywords by category
        """
        job_id = task_data.get("job_id")
        job_description = task_data.get("job_description")
        
        if not job_description and job_id:
            # Get job description from database
            job = await job_repository.get_by_id(job_id)
            if not job:
                raise AgentError(f"Job not found: {job_id}")
            job_description = job.description
        
        if not job_description:
            raise AgentError("job_description or job_id is required")
        
        try:
            keywords = await self.ollama.extract_keywords(job_description)
            
            self.logger.info(f"Extracted keywords for job {job_id or 'direct'}")
            
            return {
                "success": True,
                "keywords": keywords,
                "extracted_at": datetime.utcnow().isoformat()
            }
            
        except OllamaError as e:
            self.logger.error(f"Keyword extraction failed: {e}")
            raise AgentError(f"Keyword extraction failed: {e}")
    
    async def _analyze_resume_content(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze resume content for ATS compatibility and suggestions.
        
        Args:
            task_data: Task data with resume_id or resume_content
            
        Returns:
            Analysis results and suggestions
        """
        resume_id = task_data.get("resume_id")
        resume_content = task_data.get("resume_content")
        
        if not resume_content and resume_id:
            # Get resume from database
            resume = await resume_repository.get_by_id(resume_id)
            if not resume:
                raise AgentError(f"Resume not found: {resume_id}")
            resume_content = resume.content
        
        if not resume_content:
            raise AgentError("resume_content or resume_id is required")
        
        try:
            # Use AI to analyze resume
            analysis_prompt = f"""
            Analyze the following resume for ATS compatibility and provide improvement suggestions:
            
            Resume Content:
            {resume_content}
            
            Please provide analysis in JSON format:
            {{
                "ats_score": 85,
                "strengths": ["strength1", "strength2"],
                "weaknesses": ["weakness1", "weakness2"],
                "suggestions": ["suggestion1", "suggestion2"],
                "missing_sections": ["section1", "section2"],
                "keyword_density": {{"keyword": 3}},
                "overall_assessment": "Brief overall assessment"
            }}
            """
            
            response = await self.ollama.generate_response(
                prompt=analysis_prompt,
                temperature=0.1
            )
            
            # Parse response
            import json
            import re
            try:
                analysis = json.loads(response)
            except json.JSONDecodeError:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    raise AgentError("Failed to parse analysis response")
            
            self.logger.info(f"Analyzed resume {resume_id or 'direct'}")
            
            return {
                "success": True,
                "analysis": analysis,
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
        except OllamaError as e:
            self.logger.error(f"Resume analysis failed: {e}")
            raise AgentError(f"Resume analysis failed: {e}")
        except Exception as e:
            self.logger.error(f"Resume analysis error: {e}")
            raise AgentError(f"Resume analysis error: {e}")
    
    async def optimize_resume_for_job(
        self,
        user_id: str,
        job_id: str,
        resume_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Public method to optimize resume for a job.
        
        Args:
            user_id: User ID
            job_id: Job ID
            resume_id: Optional specific resume ID
            
        Returns:
            Optimization result
        """
        return await self.execute_task({
            "action": "optimize_resume",
            "user_id": user_id,
            "job_id": job_id,
            "resume_id": resume_id
        })
    
    async def extract_job_keywords(
        self,
        job_id: Optional[str] = None,
        job_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Public method to extract keywords from job description.
        
        Args:
            job_id: Job ID (if extracting from stored job)
            job_description: Direct job description text
            
        Returns:
            Keyword extraction result
        """
        return await self.execute_task({
            "action": "extract_keywords",
            "job_id": job_id,
            "job_description": job_description
        })
    
    async def analyze_resume(
        self,
        resume_id: Optional[str] = None,
        resume_content: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Public method to analyze resume content.
        
        Args:
            resume_id: Resume ID (if analyzing stored resume)
            resume_content: Direct resume content
            
        Returns:
            Analysis result
        """
        return await self.execute_task({
            "action": "analyze_resume",
            "resume_id": resume_id,
            "resume_content": resume_content
        })
    
    async def _suggest_resume_improvements(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest resume improvements based on job description analysis.
        
        Args:
            task_data: Task data with resume_id/content and job_id/description
            
        Returns:
            Improvement suggestions and analysis
        """
        resume_id = task_data.get("resume_id")
        resume_content = task_data.get("resume_content")
        job_id = task_data.get("job_id")
        job_description = task_data.get("job_description")
        
        # Get resume content
        if not resume_content and resume_id:
            resume = await resume_repository.get_by_id(resume_id)
            if not resume:
                raise AgentError(f"Resume not found: {resume_id}")
            resume_content = resume.content
        
        # Get job description
        if not job_description and job_id:
            job = await job_repository.get_by_id(job_id)
            if not job:
                raise AgentError(f"Job not found: {job_id}")
            job_description = job.description
        
        if not resume_content or not job_description:
            raise AgentError("resume_content and job_description are required")
        
        try:
            suggestions = nlp_service.suggest_resume_improvements(
                resume_content=resume_content,
                job_description=job_description
            )
            
            self.logger.info(f"Generated improvement suggestions for resume {resume_id or 'direct'}")
            
            return {
                "success": True,
                "suggestions": suggestions,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Improvement suggestion failed: {e}")
            raise AgentError(f"Improvement suggestion failed: {e}")
    
    async def _validate_ats_compliance(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resume ATS compliance.
        
        Args:
            task_data: Task data with resume_id or resume_content
            
        Returns:
            ATS compliance validation results
        """
        resume_id = task_data.get("resume_id")
        resume_content = task_data.get("resume_content")
        
        if not resume_content and resume_id:
            resume = await resume_repository.get_by_id(resume_id)
            if not resume:
                raise AgentError(f"Resume not found: {resume_id}")
            resume_content = resume.content
        
        if not resume_content:
            raise AgentError("resume_content or resume_id is required")
        
        try:
            validation_result = ATSOptimizer.validate_ats_compliance(resume_content)
            
            self.logger.info(f"Validated ATS compliance for resume {resume_id or 'direct'}")
            
            return {
                "success": True,
                "validation": validation_result,
                "validated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"ATS validation failed: {e}")
            raise AgentError(f"ATS validation failed: {e}")
    
    async def suggest_improvements(
        self,
        resume_id: Optional[str] = None,
        resume_content: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        job_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Public method to suggest resume improvements.
        
        Args:
            resume_id: Resume ID (if analyzing stored resume)
            resume_content: Direct resume content
            job_id: Job ID (if analyzing for stored job)
            job_description: Direct job description
            
        Returns:
            Improvement suggestions
        """
        return await self.execute_task({
            "action": "suggest_improvements",
            "resume_id": resume_id,
            "resume_content": resume_content,
            "job_id": job_id,
            "job_description": job_description
        })
    
    async def validate_ats_compliance(
        self,
        resume_id: Optional[str] = None,
        resume_content: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Public method to validate ATS compliance.
        
        Args:
            resume_id: Resume ID (if validating stored resume)
            resume_content: Direct resume content
            
        Returns:
            ATS compliance validation
        """
        return await self.execute_task({
            "action": "validate_ats",
            "resume_id": resume_id,
            "resume_content": resume_content
        })
    
    async def _generate_resume_pdf(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate PDF for resume content.
        
        Args:
            task_data: Task data with resume_id/content, user_id, job_id, resume_type
            
        Returns:
            PDF generation result
        """
        user_id = task_data.get("user_id")
        resume_id = task_data.get("resume_id")
        resume_content = task_data.get("resume_content")
        job_id = task_data.get("job_id")
        resume_type = task_data.get("resume_type", "original")
        
        if not user_id:
            raise AgentError("user_id is required for PDF generation")
        
        # Get resume content
        if not resume_content and resume_id:
            resume = await resume_repository.get_by_id(resume_id)
            if not resume:
                raise AgentError(f"Resume not found: {resume_id}")
            resume_content = resume.content
        
        if not resume_content:
            raise AgentError("resume_content or resume_id is required")
        
        try:
            pdf_result = await pdf_service.generate_resume_pdf(
                resume_content=resume_content,
                user_id=user_id,
                job_id=job_id,
                resume_type=resume_type
            )
            
            # Update resume record with file path if resume_id provided
            if resume_id:
                resume = await resume_repository.get_by_id(resume_id)
                if resume:
                    resume.file_path = pdf_result["file_path"]
                    await resume_repository.update(resume_id, resume)
            
            self.logger.info(f"Generated PDF for resume {resume_id or 'direct'}")
            
            return pdf_result
            
        except PDFGenerationError as e:
            self.logger.error(f"PDF generation failed: {e}")
            raise AgentError(f"PDF generation failed: {e}")
        except Exception as e:
            self.logger.error(f"PDF generation error: {e}")
            raise AgentError(f"PDF generation error: {e}")
    
    async def _list_user_resumes(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """List all resume files for a user.
        
        Args:
            task_data: Task data with user_id
            
        Returns:
            List of user's resume files
        """
        user_id = task_data.get("user_id")
        
        if not user_id:
            raise AgentError("user_id is required")
        
        try:
            resumes = await pdf_service.list_user_resumes(user_id)
            
            self.logger.info(f"Listed {len(resumes)} resumes for user {user_id}")
            
            return {
                "success": True,
                "resumes": resumes,
                "count": len(resumes),
                "listed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Resume listing failed: {e}")
            raise AgentError(f"Resume listing failed: {e}")
    
    async def generate_pdf(
        self,
        user_id: str,
        resume_id: Optional[str] = None,
        resume_content: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        resume_type: str = "original"
    ) -> Dict[str, Any]:
        """Public method to generate PDF for resume.
        
        Args:
            user_id: User ID
            resume_id: Resume ID (if generating for stored resume)
            resume_content: Direct resume content
            job_id: Job ID (for optimized resumes)
            resume_type: Resume type (original, optimized)
            
        Returns:
            PDF generation result
        """
        return await self.execute_task({
            "action": "generate_pdf",
            "user_id": user_id,
            "resume_id": resume_id,
            "resume_content": resume_content,
            "job_id": job_id,
            "resume_type": resume_type
        })
    
    async def list_user_resumes(self, user_id: str) -> Dict[str, Any]:
        """Public method to list user's resume files.
        
        Args:
            user_id: User ID
            
        Returns:
            List of user's resume files
        """
        return await self.execute_task({
            "action": "list_resumes",
            "user_id": user_id
        })
    
    async def _get_version_history(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get version history for user.
        
        Args:
            task_data: Task data with user_id
            
        Returns:
            Version history and statistics
        """
        user_id = task_data.get("user_id")
        
        if not user_id:
            raise AgentError("user_id is required")
        
        try:
            # Get version tree and statistics
            version_tree = await resume_versioning_service.get_version_tree(user_id)
            statistics = await resume_versioning_service.get_version_statistics(user_id)
            
            self.logger.info(f"Retrieved version history for user {user_id}")
            
            return {
                "success": True,
                "version_tree": version_tree,
                "statistics": statistics,
                "retrieved_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Version history retrieval failed: {e}")
            raise AgentError(f"Version history retrieval failed: {e}")
    
    async def _get_optimization_history(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get optimization history for user.
        
        Args:
            task_data: Task data with user_id and optional job_id
            
        Returns:
            Optimization history
        """
        user_id = task_data.get("user_id")
        job_id = task_data.get("job_id")
        
        if not user_id:
            raise AgentError("user_id is required")
        
        try:
            optimization_history = await resume_versioning_service.get_optimization_history(
                user_id=user_id,
                job_id=job_id
            )
            
            self.logger.info(f"Retrieved optimization history for user {user_id}")
            
            return {
                "success": True,
                "optimization_history": optimization_history,
                "count": len(optimization_history),
                "job_id_filter": job_id,
                "retrieved_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Optimization history retrieval failed: {e}")
            raise AgentError(f"Optimization history retrieval failed: {e}")
    
    async def get_version_history(self, user_id: str) -> Dict[str, Any]:
        """Public method to get version history for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Version history and statistics
        """
        return await self.execute_task({
            "action": "get_version_history",
            "user_id": user_id
        })
    
    async def get_optimization_history(
        self,
        user_id: str,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Public method to get optimization history for user.
        
        Args:
            user_id: User ID
            job_id: Optional job ID to filter by
            
        Returns:
            Optimization history
        """
        return await self.execute_task({
            "action": "get_optimization_history",
            "user_id": user_id,
            "job_id": job_id
        })


# Global agent instance
resume_builder_agent = ResumeBuilderAgent()