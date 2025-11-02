"""Resume Builder API endpoints."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, Field

from app.mcp.resume_builder_agent import resume_builder_agent
from app.services.pdf_service import pdf_service
from app.repositories.resume_repository import resume_repository
from app.repositories.job_repository import job_repository


# Request/Response models
class OptimizeResumeRequest(BaseModel):
    """Request model for resume optimization."""
    user_id: str = Field(..., description="User ID")
    job_id: str = Field(..., description="Job ID to optimize for")
    resume_id: Optional[str] = Field(None, description="Specific resume ID (optional)")


class ExtractKeywordsRequest(BaseModel):
    """Request model for keyword extraction."""
    job_id: Optional[str] = Field(None, description="Job ID")
    job_description: Optional[str] = Field(None, description="Direct job description")


class AnalyzeResumeRequest(BaseModel):
    """Request model for resume analysis."""
    resume_id: Optional[str] = Field(None, description="Resume ID")
    resume_content: Optional[Dict[str, Any]] = Field(None, description="Direct resume content")


class SuggestImprovementsRequest(BaseModel):
    """Request model for improvement suggestions."""
    resume_id: Optional[str] = Field(None, description="Resume ID")
    resume_content: Optional[Dict[str, Any]] = Field(None, description="Direct resume content")
    job_id: Optional[str] = Field(None, description="Job ID")
    job_description: Optional[str] = Field(None, description="Direct job description")


class GeneratePDFRequest(BaseModel):
    """Request model for PDF generation."""
    user_id: str = Field(..., description="User ID")
    resume_id: Optional[str] = Field(None, description="Resume ID")
    resume_content: Optional[Dict[str, Any]] = Field(None, description="Direct resume content")
    job_id: Optional[str] = Field(None, description="Job ID for optimized resumes")
    resume_type: str = Field("original", description="Resume type (original, optimized)")


# Response models
class OptimizationResponse(BaseModel):
    """Response model for resume optimization."""
    success: bool
    resume_id: str
    file_path: str
    keywords_added: List[str]
    optimization_notes: str
    optimization_score: float
    created_at: str


class KeywordExtractionResponse(BaseModel):
    """Response model for keyword extraction."""
    success: bool
    keywords: Dict[str, List[str]]
    extracted_at: str


class AnalysisResponse(BaseModel):
    """Response model for resume analysis."""
    success: bool
    analysis: Dict[str, Any]
    analyzed_at: str


class ImprovementSuggestionsResponse(BaseModel):
    """Response model for improvement suggestions."""
    success: bool
    suggestions: Dict[str, Any]
    generated_at: str


class PDFGenerationResponse(BaseModel):
    """Response model for PDF generation."""
    success: bool
    file_path: str
    file_metadata: Dict[str, Any]
    resume_type: str
    generated_at: str


class VersionHistoryResponse(BaseModel):
    """Response model for version history."""
    success: bool
    version_tree: Dict[str, Any]
    statistics: Dict[str, Any]
    retrieved_at: str


class OptimizationHistoryResponse(BaseModel):
    """Response model for optimization history."""
    success: bool
    optimization_history: List[Dict[str, Any]]
    count: int
    job_id_filter: Optional[str]
    retrieved_at: str


# Router setup
router = APIRouter(prefix="/resume-builder", tags=["Resume Builder"])
logger = logging.getLogger(__name__)


@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_resume(request: OptimizeResumeRequest):
    """Optimize resume for a specific job posting.
    
    This endpoint uses AI to optimize a resume for a specific job,
    incorporating relevant keywords and ATS-friendly formatting.
    """
    try:
        result = await resume_builder_agent.optimize_resume_for_job(
            user_id=request.user_id,
            job_id=request.job_id,
            resume_id=request.resume_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Resume optimization failed")
        
        return OptimizationResponse(**result)
        
    except Exception as e:
        logger.error(f"Resume optimization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-keywords", response_model=KeywordExtractionResponse)
async def extract_keywords(request: ExtractKeywordsRequest):
    """Extract keywords from job description.
    
    Analyzes job description to extract relevant keywords and skills
    that should be included in a resume.
    """
    try:
        if not request.job_id and not request.job_description:
            raise HTTPException(
                status_code=400, 
                detail="Either job_id or job_description is required"
            )
        
        result = await resume_builder_agent.extract_job_keywords(
            job_id=request.job_id,
            job_description=request.job_description
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Keyword extraction failed")
        
        return KeywordExtractionResponse(**result)
        
    except Exception as e:
        logger.error(f"Keyword extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_resume(request: AnalyzeResumeRequest):
    """Analyze resume content for ATS compatibility and suggestions.
    
    Provides detailed analysis of resume content including ATS score,
    strengths, weaknesses, and improvement suggestions.
    """
    try:
        if not request.resume_id and not request.resume_content:
            raise HTTPException(
                status_code=400,
                detail="Either resume_id or resume_content is required"
            )
        
        result = await resume_builder_agent.analyze_resume(
            resume_id=request.resume_id,
            resume_content=request.resume_content
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Resume analysis failed")
        
        return AnalysisResponse(**result)
        
    except Exception as e:
        logger.error(f"Resume analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-improvements", response_model=ImprovementSuggestionsResponse)
async def suggest_improvements(request: SuggestImprovementsRequest):
    """Suggest resume improvements based on job description analysis.
    
    Provides specific suggestions for improving resume content
    to better match job requirements.
    """
    try:
        if not request.resume_id and not request.resume_content:
            raise HTTPException(
                status_code=400,
                detail="Either resume_id or resume_content is required"
            )
        
        if not request.job_id and not request.job_description:
            raise HTTPException(
                status_code=400,
                detail="Either job_id or job_description is required"
            )
        
        result = await resume_builder_agent.suggest_improvements(
            resume_id=request.resume_id,
            resume_content=request.resume_content,
            job_id=request.job_id,
            job_description=request.job_description
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Improvement suggestion failed")
        
        return ImprovementSuggestionsResponse(**result)
        
    except Exception as e:
        logger.error(f"Improvement suggestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-ats")
async def validate_ats_compliance(request: AnalyzeResumeRequest):
    """Validate resume ATS compliance.
    
    Checks resume against ATS-friendly formatting rules
    and provides compliance score and suggestions.
    """
    try:
        if not request.resume_id and not request.resume_content:
            raise HTTPException(
                status_code=400,
                detail="Either resume_id or resume_content is required"
            )
        
        result = await resume_builder_agent.validate_ats_compliance(
            resume_id=request.resume_id,
            resume_content=request.resume_content
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="ATS validation failed")
        
        return result
        
    except Exception as e:
        logger.error(f"ATS validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-pdf", response_model=PDFGenerationResponse)
async def generate_pdf(request: GeneratePDFRequest):
    """Generate PDF for resume content.
    
    Creates a professionally formatted PDF resume
    from resume content dictionary.
    """
    try:
        if not request.resume_id and not request.resume_content:
            raise HTTPException(
                status_code=400,
                detail="Either resume_id or resume_content is required"
            )
        
        result = await resume_builder_agent.generate_pdf(
            user_id=request.user_id,
            resume_id=request.resume_id,
            resume_content=request.resume_content,
            job_id=request.job_id,
            resume_type=request.resume_type
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="PDF generation failed")
        
        return PDFGenerationResponse(**result)
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resumes/{user_id}")
async def list_user_resumes(user_id: str):
    """List all resume files for a user.
    
    Returns metadata for all resume files (original and optimized)
    stored for the specified user.
    """
    try:
        result = await resume_builder_agent.list_user_resumes(user_id)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Resume listing failed")
        
        return result
        
    except Exception as e:
        logger.error(f"Resume listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version-history/{user_id}", response_model=VersionHistoryResponse)
async def get_version_history(user_id: str):
    """Get version history for user's resumes.
    
    Returns complete version tree and statistics
    for all resume versions created by the user.
    """
    try:
        result = await resume_builder_agent.get_version_history(user_id)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Version history retrieval failed")
        
        return VersionHistoryResponse(**result)
        
    except Exception as e:
        logger.error(f"Version history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimization-history/{user_id}", response_model=OptimizationHistoryResponse)
async def get_optimization_history(user_id: str, job_id: Optional[str] = None):
    """Get optimization history for user.
    
    Returns history of all resume optimizations performed,
    optionally filtered by job ID.
    """
    try:
        result = await resume_builder_agent.get_optimization_history(
            user_id=user_id,
            job_id=job_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Optimization history retrieval failed")
        
        return OptimizationHistoryResponse(**result)
        
    except Exception as e:
        logger.error(f"Optimization history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{user_id}/{filename}")
async def download_resume_pdf(user_id: str, filename: str):
    """Download resume PDF file.
    
    Returns the PDF file content for download.
    """
    try:
        # Construct file path
        from pathlib import Path
        file_path = Path(pdf_service.file_manager.base_path) / user_id / filename
        
        # Get PDF content
        pdf_content = await pdf_service.get_resume_pdf(str(file_path))
        
        if not pdf_content:
            raise HTTPException(status_code=404, detail="Resume PDF not found")
        
        from fastapi.responses import Response
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"PDF download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/resumes/{user_id}/{filename}")
async def delete_resume_pdf(user_id: str, filename: str):
    """Delete resume PDF file.
    
    Removes the specified resume PDF file from storage.
    """
    try:
        # Construct file path
        from pathlib import Path
        file_path = Path(pdf_service.file_manager.base_path) / user_id / filename
        
        # Delete PDF
        success = await pdf_service.delete_resume_pdf(str(file_path))
        
        if not success:
            raise HTTPException(status_code=404, detail="Resume PDF not found")
        
        return {"success": True, "message": "Resume PDF deleted successfully"}
        
    except Exception as e:
        logger.error(f"PDF deletion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint for Resume Builder service.
    
    Returns the health status of the Resume Builder Agent
    and its dependencies.
    """
    try:
        # Check agent status
        agent_status = await resume_builder_agent.get_status()
        
        # Check Ollama service
        from app.services.ollama_service import ollama_service
        ollama_health = await ollama_service.health_check()
        
        # Check NLP service
        from app.services.nlp_service import nlp_service
        nlp_initialized = nlp_service._initialized
        
        return {
            "status": "healthy" if agent_status["status"] == "running" else "unhealthy",
            "agent_status": agent_status,
            "ollama_service": ollama_health,
            "nlp_service": {"initialized": nlp_initialized},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }