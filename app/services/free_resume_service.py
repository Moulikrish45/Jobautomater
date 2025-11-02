"""Free resume optimization using Gemini AI."""

import httpx
import json
import os
import io
import logging
from typing import List, Dict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class FreeResumeService:
    """Resume analysis using Google Gemini AI."""
    
    def __init__(self):
        self.storage_path = Path("data/resumes")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "AIzaSyBX-Ztg2I6C5zBrrHxRkCatpAiF2P8JDBE")
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.gemini_api_key}"
    
    async def parse_resume(self, file_content: bytes, filename: str) -> Dict:
        """Parse resume - ONE API call only."""
        text = self.extract_text(file_content, filename)
        
        logger.info(f"Resume text length: {len(text)} chars")
        logger.info(f"First 200 chars: {text[:200]}")
        
        prompt = f"""Extract from this resume in JSON:
{{
  "skills": ["skill1", "skill2"],
  "experience": ["job title - years"],
  "education": ["degree - institution"],
  "job_titles": ["suitable job titles"],
  "search_keywords": ["top 5 keywords for job search"],
  "summary": "brief summary"
}}

Resume:
{text[:4000]}"""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.gemini_url, json={"contents": [{"parts": [{"text": prompt}]}]})
                result = r.json()
                
                logger.info(f"Gemini API Response: {json.dumps(result, indent=2)}")
                
                response_text = result['candidates'][0]['content']['parts'][0]['text']
                logger.info(f"Gemini extracted text: {response_text}")
                
                json_text = response_text.strip()
                if '```json' in json_text:
                    json_text = json_text.split('```json')[1].split('```')[0]
                elif '```' in json_text:
                    json_text = json_text.split('```')[1].split('```')[0]
                
                parsed = json.loads(json_text.strip())
                logger.info(f"Parsed JSON: {parsed}")
                
                return {
                    "text": text[:500],
                    "skills": parsed.get('skills', []),
                    "experience": parsed.get('experience', []),
                    "education": parsed.get('education', []),
                    "job_titles": parsed.get('job_titles', []),
                    "search_keywords": parsed.get('search_keywords', []),
                    "summary": parsed.get('summary', ''),
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Parse error: {str(e)}", exc_info=True)
            return {
                "text": text[:500],
                "skills": [],
                "experience": [],
                "education": [],
                "job_titles": ['developer'],
                "search_keywords": ['software', 'developer'],
                "summary": text[:200],
                "filename": filename,
                "parsed_at": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def extract_text(self, file_content: bytes, filename: str) -> str:
        """Extract text from PDF, Word, or text file."""
        ext = filename.lower().split('.')[-1]
        
        # Word documents
        if ext in ['docx', 'doc'] and DOCX_AVAILABLE:
            try:
                doc = docx.Document(io.BytesIO(file_content))
                text = '\n'.join(para.text for para in doc.paragraphs)
                logger.info(f"Extracted {len(text)} chars from Word doc")
                return text
            except Exception as e:
                logger.error(f"Word extraction failed: {e}")
        
        # PDF files
        if ext == 'pdf' and PDF_AVAILABLE:
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                text = '\n'.join(page.extract_text() for page in pdf_reader.pages)
                logger.info(f"Extracted {len(text)} chars from PDF")
                return text
            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
        
        # Text files
        text = file_content.decode('utf-8', errors='ignore')
        logger.info(f"Decoded {len(text)} chars as text")
        return text
    
    async def save_resume(self, user_id: str, resume_data: Dict) -> str:
        """Save resume to local storage."""
        user_path = self.storage_path / user_id
        user_path.mkdir(exist_ok=True)
        
        file_path = user_path / f"resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(file_path, 'w') as f:
            json.dump(resume_data, f, indent=2)
        
        return str(file_path)
    
    def extract_search_keywords(self, resume_data: Dict) -> List[str]:
        """Get search keywords from resume."""
        keywords = resume_data.get('search_keywords', [])
        if keywords:
            return keywords[:5]
        return resume_data.get('skills', ['software', 'developer'])[:3]
    
    def calculate_ats_score(self, resume_data: Dict, job_desc: str) -> Dict:
        """Simple keyword matching - NO API calls."""
        resume_skills = set(s.lower() for s in resume_data.get('skills', []))
        job_words = set(job_desc.lower().split())
        
        matched = [s for s in resume_skills if any(s in w for w in job_words)]
        score = min(100, len(matched) * 10)
        
        return {
            "score": float(score),
            "matched_keywords": matched[:10],
            "missing_keywords": [],
            "total_keywords": len(matched),
            "recommendation": "High" if score >= 70 else "Medium" if score >= 40 else "Low"
        }
    
    def match_jobs_to_resume(self, resume_data: Dict, jobs: List[Dict]) -> List[Dict]:
        """Match jobs - simple keyword scoring."""
        matched_jobs = []
        
        for job in jobs:
            ats = self.calculate_ats_score(resume_data, job.get('description', ''))
            matched_jobs.append({
                **job,
                "ats_score": ats["score"],
                "ats_recommendation": ats["recommendation"],
                "matched_keywords": ats["matched_keywords"],
                "missing_keywords": ats["missing_keywords"]
            })
        
        return sorted(matched_jobs, key=lambda x: x['ats_score'], reverse=True)
    
    async def get_job_titles_from_gemini(self, skills: List[str]) -> List[str]:
        """Ask Gemini what job titles match these skills."""
        skills_text = ', '.join(skills[:10])
        prompt = f"""Based on these skills: {skills_text}

List 5-7 job titles that would be perfect matches. Return ONLY a JSON array of job titles.
Example: ["Software Engineer", "Full Stack Developer"]"""
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(self.gemini_url, json={"contents": [{"parts": [{"text": prompt}]}]})
                response_text = r.json()['candidates'][0]['content']['parts'][0]['text']
                
                logger.info(f"Gemini job titles response: {response_text}")
                
                json_text = response_text.strip()
                if '```json' in json_text:
                    json_text = json_text.split('```json')[1].split('```')[0]
                elif '```' in json_text:
                    json_text = json_text.split('```')[1].split('```')[0]
                elif '[' in json_text:
                    json_text = json_text[json_text.find('['):json_text.rfind(']')+1]
                
                job_titles = json.loads(json_text.strip())
                return job_titles if isinstance(job_titles, list) else []
        except Exception as e:
            logger.error(f"Gemini job titles error: {e}")
            return skills[:3]
    
    async def auto_search_jobs(self, resume_data: Dict) -> List[Dict]:
        """Search jobs using Gemini-suggested job titles."""
        from app.utcp.free_client import FreeJobClient
        
        skills = resume_data.get('skills', [])
        job_titles = await self.get_job_titles_from_gemini(skills)
        
        logger.info(f"Searching jobs with Gemini-suggested titles: {job_titles}")
        
        client = FreeJobClient()
        try:
            jobs = await client.search_all(job_titles, location="", remote_only=False)
            return self.match_jobs_to_resume(resume_data, jobs)
        finally:
            await client.close()
