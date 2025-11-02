"""Ollama AI model service for resume optimization."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import ollama
from ollama import AsyncClient
from jinja2 import Environment, BaseLoader, Template

from app.config import settings


class OllamaError(Exception):
    """Base exception for Ollama service errors."""
    pass


class ModelNotAvailableError(OllamaError):
    """Exception raised when requested model is not available."""
    pass


class PromptTemplate:
    """Jinja2 template wrapper for AI prompts."""
    
    def __init__(self, template_string: str):
        """Initialize template with Jinja2 string.
        
        Args:
            template_string: Jinja2 template string
        """
        self.env = Environment(loader=BaseLoader())
        self.template = self.env.from_string(template_string)
    
    def render(self, **kwargs) -> str:
        """Render template with provided variables.
        
        Args:
            **kwargs: Template variables
            
        Returns:
            Rendered template string
        """
        return self.template.render(**kwargs)


class OllamaService:
    """Service for interacting with Ollama AI models."""
    
    # Default prompt templates for resume optimization
    RESUME_OPTIMIZATION_TEMPLATE = """
You are an expert resume writer and ATS optimization specialist. Your task is to optimize a resume for a specific job posting while maintaining accuracy and authenticity.

Job Description:
{{ job_description }}

Current Resume Content:
{{ resume_content }}

Instructions:
1. Analyze the job description to identify key skills, requirements, and keywords
2. Optimize the resume to include relevant keywords naturally
3. Ensure ATS-friendly formatting and structure
4. Maintain all factual information - do not fabricate experience
5. Focus on highlighting relevant experience and skills
6. Use action verbs and quantifiable achievements where possible

Please provide the optimized resume content in the following JSON format:
{
    "optimized_content": {
        "summary": "Professional summary with relevant keywords",
        "experience": [
            {
                "title": "Job title",
                "company": "Company name",
                "duration": "Start - End dates",
                "description": "Optimized job description with relevant keywords"
            }
        ],
        "skills": ["skill1", "skill2", "skill3"],
        "education": [
            {
                "degree": "Degree name",
                "institution": "Institution name",
                "year": "Graduation year"
            }
        ]
    },
    "keywords_added": ["keyword1", "keyword2"],
    "optimization_notes": "Brief explanation of changes made"
}
"""

    KEYWORD_EXTRACTION_TEMPLATE = """
Analyze the following job description and extract the most important keywords and skills that should be included in a resume for this position.

Job Description:
{{ job_description }}

Please provide the extracted keywords in the following JSON format:
{
    "technical_skills": ["skill1", "skill2"],
    "soft_skills": ["skill1", "skill2"],
    "required_keywords": ["keyword1", "keyword2"],
    "industry_terms": ["term1", "term2"],
    "experience_level": "junior/mid/senior",
    "priority_keywords": ["top_keyword1", "top_keyword2"]
}
"""
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        default_model: str = "llama2",
        timeout: float = 60.0
    ):
        """Initialize Ollama service.
        
        Args:
            host: Ollama server host URL
            default_model: Default model to use for requests
            timeout: Request timeout in seconds
        """
        self.host = host
        self.default_model = default_model
        self.timeout = timeout
        self.client = AsyncClient(host=host)
        self.logger = logging.getLogger(__name__)
        
        # Initialize prompt templates
        self.resume_template = PromptTemplate(self.RESUME_OPTIMIZATION_TEMPLATE)
        self.keyword_template = PromptTemplate(self.KEYWORD_EXTRACTION_TEMPLATE)
    
    async def check_model_availability(self, model_name: Optional[str] = None) -> bool:
        """Check if a model is available in Ollama.
        
        Args:
            model_name: Model name to check (uses default if None)
            
        Returns:
            True if model is available, False otherwise
        """
        model = model_name or self.default_model
        
        try:
            models = await self.client.list()
            available_models = [m['name'] for m in models['models']]
            return model in available_models
        except Exception as e:
            self.logger.error(f"Failed to check model availability: {e}")
            return False
    
    async def ensure_model_available(self, model_name: Optional[str] = None) -> None:
        """Ensure a model is available, pull if necessary.
        
        Args:
            model_name: Model name to ensure (uses default if None)
            
        Raises:
            ModelNotAvailableError: If model cannot be made available
        """
        model = model_name or self.default_model
        
        if await self.check_model_availability(model):
            return
        
        try:
            self.logger.info(f"Pulling model: {model}")
            await self.client.pull(model)
            self.logger.info(f"Successfully pulled model: {model}")
        except Exception as e:
            self.logger.error(f"Failed to pull model {model}: {e}")
            raise ModelNotAvailableError(f"Model {model} is not available and could not be pulled: {e}")
    
    async def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate AI response for given prompt.
        
        Args:
            prompt: Input prompt for the model
            model: Model name to use (uses default if None)
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text
            
        Raises:
            OllamaError: If generation fails
        """
        model_name = model or self.default_model
        
        try:
            # Ensure model is available
            await self.ensure_model_available(model_name)
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Generate response
            response = await self.client.chat(
                model=model_name,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens or -1
                }
            )
            
            return response['message']['content']
            
        except Exception as e:
            self.logger.error(f"Failed to generate response: {e}")
            raise OllamaError(f"Response generation failed: {e}")
    
    async def optimize_resume(
        self,
        resume_content: Dict[str, Any],
        job_description: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Optimize resume content for a specific job posting.
        
        Args:
            resume_content: Current resume content as dictionary
            job_description: Target job description
            model: Model to use for optimization
            
        Returns:
            Optimized resume data with metadata
            
        Raises:
            OllamaError: If optimization fails
        """
        try:
            # Render prompt template
            prompt = self.resume_template.render(
                resume_content=resume_content,
                job_description=job_description
            )
            
            # Generate optimized content
            response = await self.generate_response(
                prompt=prompt,
                model=model,
                temperature=0.1  # Low temperature for consistent formatting
            )
            
            # Parse JSON response (basic parsing, could be enhanced)
            import json
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                # Fallback: extract JSON from response if wrapped in text
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise OllamaError("Failed to parse optimization response as JSON")
            
            # Add metadata
            result['optimization_metadata'] = {
                'model_used': model or self.default_model,
                'optimized_at': datetime.utcnow().isoformat(),
                'original_content_hash': hash(str(resume_content))
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Resume optimization failed: {e}")
            raise OllamaError(f"Resume optimization failed: {e}")
    
    async def extract_keywords(
        self,
        job_description: str,
        model: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """Extract keywords and skills from job description.
        
        Args:
            job_description: Job description text
            model: Model to use for extraction
            
        Returns:
            Dictionary with categorized keywords
            
        Raises:
            OllamaError: If extraction fails
        """
        try:
            # Render prompt template
            prompt = self.keyword_template.render(
                job_description=job_description
            )
            
            # Generate keyword extraction
            response = await self.generate_response(
                prompt=prompt,
                model=model,
                temperature=0.1
            )
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                # Fallback parsing
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise OllamaError("Failed to parse keyword extraction response as JSON")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Keyword extraction failed: {e}")
            raise OllamaError(f"Keyword extraction failed: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Ollama service health and available models.
        
        Returns:
            Health status information
        """
        try:
            # Check if Ollama is running
            models = await self.client.list()
            
            # Check default model availability
            default_available = await self.check_model_availability(self.default_model)
            
            return {
                "status": "healthy",
                "host": self.host,
                "default_model": self.default_model,
                "default_model_available": default_available,
                "available_models": [m['name'] for m in models['models']],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global service instance
ollama_service = OllamaService(
    host=getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434'),
    default_model=getattr(settings, 'OLLAMA_DEFAULT_MODEL', 'llama2')
)