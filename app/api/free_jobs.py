"""Free job search API endpoints."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List

from app.services.free_job_service import FreeJobService
from app.utcp.free_client import FreeJobClient
from app.services.free_resume_service import FreeResumeService


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class SearchRequest(BaseModel):
    keywords: List[str]
    location: str = ""
    remote_only: bool = False
    date_posted: str = "all"  # all, today, week, month
    job_type: str = "all"  # all, fulltime, parttime, contract
    experience: str = "all"  # all, entry, mid, senior
    salary_min: int = 0
    sort_by: str = "relevance"  # relevance, date, company


@router.post("/search/free")
async def search_free_jobs(req: SearchRequest):
    """Search all free job sources with advanced filters."""
    client = FreeJobClient()
    try:
        jobs = await client.search_all(
            keywords=req.keywords,
            location=req.location,
            remote_only=req.remote_only,
            date_posted=req.date_posted,
            job_type=req.job_type,
            experience=req.experience,
            salary_min=req.salary_min,
            sort_by=req.sort_by
        )
        return {"success": True, "jobs": jobs, "count": len(jobs)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await client.close()


@router.get("/list")
async def list_jobs(skip: int = 0, limit: int = 50):
    """List all jobs from database."""
    from app.repositories.job_repository import JobRepository
    repo = JobRepository()
    try:
        jobs = await repo.find_all(skip=skip, limit=limit)
        return [{"id": str(j.id), "title": j.title, "company": j.company.name, 
                 "location": j.location.city, "url": j.url, "posted": str(j.posted_date)} 
                for j in jobs]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/upload-resume")
async def upload_resume(user_id: str, file: UploadFile = File(...), auto_search: bool = False):
    """Upload and parse resume, optionally get AI job suggestions."""
    service = FreeResumeService()
    try:
        content = await file.read()
        resume_data = await service.parse_resume(content, file.filename)
        file_path = await service.save_resume(user_id, resume_data)
        
        result = {
            "success": True,
            "resume_data": resume_data,
            "file_path": file_path,
            "skills_found": len(resume_data['skills']),
            "experience_found": len(resume_data['experience']),
            "search_keywords": resume_data.get('search_keywords', [])
        }
        
        if auto_search and resume_data.get('skills'):
            job_titles = await service.get_job_titles_from_gemini(resume_data['skills'])
            result["ai_suggested_titles"] = job_titles
        
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/search-with-resume")
async def search_with_resume(user_id: str):
    """Search jobs using Gemini AI to suggest job titles from skills."""
    service = FreeResumeService()
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from pathlib import Path
        import json
        
        user_path = Path("data/resumes") / user_id
        if not user_path.exists():
            raise HTTPException(400, "No resume found. Upload resume first.")
        
        resume_files = sorted(user_path.glob("resume_*.json"), reverse=True)
        if not resume_files:
            raise HTTPException(400, "No resume found. Upload resume first.")
        
        with open(resume_files[0]) as f:
            resume_data = json.load(f)
        
        job_titles = await service.get_job_titles_from_gemini(resume_data.get('skills', []))
        matched_jobs = await service.auto_search_jobs(resume_data)
        
        logger.info(f"Found {len(matched_jobs)} total jobs")
        logger.info(f"Returning top 20: {len(matched_jobs[:20])} jobs")
        
        return {
            "success": True,
            "ai_suggested_titles": job_titles,
            "matched_jobs": matched_jobs[:20],
            "total_jobs_found": len(matched_jobs),
            "high_match_count": len([j for j in matched_jobs if j.get('ats_score', 0) >= 70])
        }
    except Exception as e:
        logger.error(f"Search error: {str(e)}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/match-resume")
async def match_resume_to_jobs(req: SearchRequest, user_id: str):
    """Search jobs with custom filters and match to resume."""
    job_client = FreeJobClient()
    resume_service = FreeResumeService()
    
    try:
        from pathlib import Path
        import json
        
        user_path = Path("data/resumes") / user_id
        if not user_path.exists():
            raise HTTPException(400, "No resume found. Upload resume first.")
        
        resume_files = sorted(user_path.glob("resume_*.json"), reverse=True)
        if not resume_files:
            raise HTTPException(400, "No resume found. Upload resume first.")
        
        with open(resume_files[0]) as f:
            resume_data = json.load(f)
        
        # Search jobs
        jobs = await job_client.search_all(
            keywords=req.keywords,
            location=req.location,
            remote_only=req.remote_only,
            date_posted=req.date_posted,
            job_type=req.job_type,
            experience=req.experience,
            salary_min=req.salary_min,
            sort_by=req.sort_by
        )
        
        # Match jobs to resume
        matched_jobs = resume_service.match_jobs_to_resume(resume_data, jobs)
        
        return {
            "success": True,
            "jobs": matched_jobs,
            "count": len(matched_jobs),
            "resume_skills": resume_data['skills'],
            "high_match_count": len([j for j in matched_jobs if j['ats_score'] >= 70]),
            "medium_match_count": len([j for j in matched_jobs if 50 <= j['ats_score'] < 70]),
            "low_match_count": len([j for j in matched_jobs if j['ats_score'] < 50])
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await job_client.close()


@router.get("/ats-score/{user_id}")
async def get_ats_score(user_id: str, job_description: str):
    """Calculate ATS score."""
    service = FreeResumeService()
    
    try:
        from pathlib import Path
        import json
        
        user_path = Path("data/resumes") / user_id
        if not user_path.exists():
            raise HTTPException(400, "No resume found")
        
        resume_files = sorted(user_path.glob("resume_*.json"), reverse=True)
        if not resume_files:
            raise HTTPException(400, "No resume found")
        
        with open(resume_files[0]) as f:
            resume_data = json.load(f)
        
        ats_result = service.calculate_ats_score(resume_data, job_description)
        
        return {"success": True, **ats_result}
    except Exception as e:
        raise HTTPException(500, str(e))
