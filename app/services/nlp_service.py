"""NLP service for resume analysis and optimization using spaCy and NLTK."""

import asyncio
import logging
import re
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import Counter
from datetime import datetime

import spacy
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class NLPServiceError(Exception):
    """Base exception for NLP service errors."""
    pass


class ModelNotLoadedError(NLPServiceError):
    """Exception raised when required NLP models are not loaded."""
    pass


class ATSOptimizer:
    """ATS-friendly formatting rules and validation."""
    
    # ATS-friendly formatting rules
    ATS_RULES = {
        "use_standard_headings": [
            "summary", "experience", "education", "skills", 
            "certifications", "projects", "achievements"
        ],
        "avoid_graphics": True,
        "avoid_tables": True,
        "avoid_headers_footers": True,
        "use_standard_fonts": ["Arial", "Calibri", "Times New Roman"],
        "font_size_range": (10, 12),
        "use_bullet_points": True,
        "avoid_special_characters": ["•", "→", "★"],
        "standard_date_format": r"\d{4}-\d{4}|\w+ \d{4} - \w+ \d{4}",
        "include_keywords": True,
        "keyword_density_range": (2, 8),  # percentage
        "max_line_length": 80
    }
    
    @classmethod
    def validate_ats_compliance(cls, resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resume content against ATS rules.
        
        Args:
            resume_content: Resume content dictionary
            
        Returns:
            Validation results with score and suggestions
        """
        score = 100
        issues = []
        suggestions = []
        
        # Check for standard sections
        required_sections = {"summary", "experience", "skills"}
        available_sections = set(resume_content.keys())
        missing_sections = required_sections - available_sections
        
        if missing_sections:
            score -= len(missing_sections) * 10
            issues.append(f"Missing required sections: {', '.join(missing_sections)}")
            suggestions.append(f"Add missing sections: {', '.join(missing_sections)}")
        
        # Check experience section format
        if "experience" in resume_content:
            experience = resume_content["experience"]
            if isinstance(experience, list):
                for i, job in enumerate(experience):
                    if not isinstance(job, dict):
                        score -= 5
                        issues.append(f"Experience entry {i+1} is not properly structured")
                        continue
                    
                    # Check for required fields
                    required_fields = {"title", "company", "duration"}
                    job_fields = set(job.keys())
                    missing_fields = required_fields - job_fields
                    
                    if missing_fields:
                        score -= len(missing_fields) * 3
                        issues.append(f"Experience entry {i+1} missing: {', '.join(missing_fields)}")
        
        # Check skills section
        if "skills" in resume_content:
            skills = resume_content["skills"]
            if isinstance(skills, list) and len(skills) < 5:
                score -= 10
                issues.append("Skills section has fewer than 5 skills")
                suggestions.append("Add more relevant skills (aim for 8-12 skills)")
        
        return {
            "ats_score": max(0, score),
            "issues": issues,
            "suggestions": suggestions,
            "compliant": score >= 80
        }
    
    @classmethod
    def optimize_formatting(cls, resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """Apply ATS-friendly formatting to resume content.
        
        Args:
            resume_content: Original resume content
            
        Returns:
            ATS-optimized resume content
        """
        optimized = resume_content.copy()
        
        # Standardize section names
        section_mapping = {
            "professional_summary": "summary",
            "work_experience": "experience",
            "technical_skills": "skills",
            "education_background": "education"
        }
        
        for old_name, new_name in section_mapping.items():
            if old_name in optimized:
                optimized[new_name] = optimized.pop(old_name)
        
        # Format experience section
        if "experience" in optimized and isinstance(optimized["experience"], list):
            for job in optimized["experience"]:
                if isinstance(job, dict):
                    # Ensure description uses bullet points
                    if "description" in job:
                        desc = job["description"]
                        if isinstance(desc, str):
                            # Convert to bullet points if not already
                            if not desc.strip().startswith("•") and not desc.strip().startswith("-"):
                                sentences = sent_tokenize(desc)
                                job["description"] = "\n".join([f"• {sent.strip()}" for sent in sentences])
        
        # Format skills section
        if "skills" in optimized:
            skills = optimized["skills"]
            if isinstance(skills, str):
                # Convert comma-separated string to list
                optimized["skills"] = [skill.strip() for skill in skills.split(",")]
            elif isinstance(skills, list):
                # Clean up skill names
                optimized["skills"] = [skill.strip() for skill in skills if skill.strip()]
        
        return optimized


class NLPService:
    """Service for NLP-based resume analysis and optimization."""
    
    def __init__(self):
        """Initialize NLP service with required models."""
        self.logger = logging.getLogger(__name__)
        self.spacy_model = None
        self.lemmatizer = None
        self.stop_words = None
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize NLP models and resources."""
        if self._initialized:
            return
        
        try:
            self.logger.info("Initializing NLP service...")
            
            # Download required NLTK data
            await self._download_nltk_data()
            
            # Load spaCy model
            try:
                self.spacy_model = spacy.load("en_core_web_sm")
            except OSError:
                self.logger.warning("spaCy model 'en_core_web_sm' not found. Install with: python -m spacy download en_core_web_sm")
                # Use basic tokenization as fallback
                self.spacy_model = None
            
            # Initialize NLTK components
            self.lemmatizer = WordNetLemmatizer()
            self.stop_words = set(stopwords.words('english'))
            
            self._initialized = True
            self.logger.info("NLP service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize NLP service: {e}")
            raise NLPServiceError(f"NLP service initialization failed: {e}")
    
    async def _download_nltk_data(self) -> None:
        """Download required NLTK data."""
        required_data = [
            'punkt', 'punkt_tab', 'stopwords', 'wordnet', 'averaged_perceptron_tagger', 'omw-1.4'
        ]
        
        for data_name in required_data:
            try:
                # Try to find the data
                if data_name == 'punkt_tab':
                    nltk.data.find('tokenizers/punkt_tab/english/')
                elif data_name == 'punkt':
                    nltk.data.find('tokenizers/punkt/english.pickle')
                elif data_name == 'stopwords':
                    nltk.data.find('corpora/stopwords/english')
                elif data_name == 'wordnet':
                    nltk.data.find('corpora/wordnet')
                elif data_name == 'averaged_perceptron_tagger':
                    nltk.data.find('taggers/averaged_perceptron_tagger/averaged_perceptron_tagger.pickle')
                elif data_name == 'omw-1.4':
                    nltk.data.find('corpora/omw-1.4')
            except LookupError:
                self.logger.info(f"Downloading NLTK data: {data_name}")
                try:
                    nltk.download(data_name, quiet=True)
                except Exception as e:
                    self.logger.warning(f"Failed to download {data_name}: {e}")
    
    def _ensure_initialized(self) -> None:
        """Ensure NLP service is initialized."""
        if not self._initialized:
            raise ModelNotLoadedError("NLP service not initialized. Call initialize() first.")
    
    def extract_keywords_from_text(
        self,
        text: str,
        max_keywords: int = 20,
        min_frequency: float = 0.01
    ) -> List[Tuple[str, float]]:
        """Extract keywords from text using TF-IDF and NLP processing.
        
        Args:
            text: Input text
            max_keywords: Maximum number of keywords to return
            min_frequency: Minimum frequency score for keyword inclusion (0.0 to 1.0)
            
        Returns:
            List of (keyword, score) tuples sorted by relevance
        """
        self._ensure_initialized()
        
        try:
            # Clean and preprocess text
            cleaned_text = self._clean_text(text)
            
            # Extract keywords using spaCy if available
            if self.spacy_model:
                keywords = self._extract_keywords_spacy(cleaned_text, max_keywords)
            else:
                keywords = self._extract_keywords_nltk(cleaned_text, max_keywords)
            
            # Filter by frequency score (now using fractional scores)
            filtered_keywords = [
                (keyword, score) for keyword, score in keywords
                if score >= min_frequency
            ]
            
            return filtered_keywords[:max_keywords]
            
        except Exception as e:
            self.logger.error(f"Keyword extraction failed: {e}")
            return []
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for processing.
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters but keep alphanumeric and basic punctuation
        # Keep + for things like "5+ years", / for "CI/CD", - for compound words
        text = re.sub(r'[^\w\s\-\.\,\;\:\+\/]', ' ', text)
        
        # Keep meaningful numbers (like "5+ years") but remove standalone numbers
        # Replace patterns like "5+" with "five plus" to preserve meaning
        text = re.sub(r'(\d+)\+', r'\1 plus', text)
        
        # Remove standalone numbers that are not part of meaningful phrases
        text = re.sub(r'\b\d{4,}\b', '', text)  # Remove years and large numbers
        text = re.sub(r'\b\d{1,2}\b(?!\s*(?:plus|years|months))', '', text)  # Remove small numbers not followed by time units
        
        return text.lower()
    
    def _extract_keywords_spacy(self, text: str, max_keywords: int) -> List[Tuple[str, float]]:
        """Extract keywords using spaCy NLP model.
        
        Args:
            text: Cleaned text
            max_keywords: Maximum keywords to return
            
        Returns:
            List of (keyword, score) tuples
        """
        doc = self.spacy_model(text)
        
        # Extract meaningful tokens (nouns, adjectives, proper nouns, verbs)
        keywords = []
        for token in doc:
            # Include more POS tags and handle compound terms
            if (token.pos_ in ['NOUN', 'ADJ', 'PROPN', 'VERB'] and
                not token.is_stop and
                not token.is_punct and
                not token.is_space and
                len(token.text) > 2 and
                token.text.isalpha()):
                # Use lemmatized form for consistency
                lemma = token.lemma_.lower().strip()
                if lemma and len(lemma) > 2:
                    keywords.append(lemma)
        
        # Also extract noun phrases for compound terms
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) <= 3:  # Limit to 3-word phrases
                phrase = chunk.text.lower().strip()
                # Clean the phrase
                phrase = ' '.join([word for word in phrase.split() if len(word) > 2])
                if phrase and len(phrase) > 4:
                    keywords.append(phrase)
        
        # Count frequency and calculate scores
        keyword_counts = Counter(keywords)
        total_keywords = len(keywords) if keywords else 1
        
        # Calculate TF scores with minimum frequency filter
        keyword_scores = []
        for keyword, count in keyword_counts.most_common():
            if count >= 1:  # Minimum frequency
                score = count / total_keywords
                keyword_scores.append((keyword, score))
        
        return keyword_scores[:max_keywords]
    
    def _extract_keywords_nltk(self, text: str, max_keywords: int) -> List[Tuple[str, float]]:
        """Extract keywords using NLTK (fallback method).
        
        Args:
            text: Cleaned text
            max_keywords: Maximum keywords to return
            
        Returns:
            List of (keyword, score) tuples
        """
        # Tokenize
        tokens = word_tokenize(text)
        
        # POS tagging to identify important words
        try:
            pos_tags = nltk.pos_tag(tokens)
            
            # Filter tokens based on POS tags (nouns, adjectives, verbs)
            important_pos = ['NN', 'NNS', 'NNP', 'NNPS', 'JJ', 'JJR', 'JJS', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ']
            keywords = []
            
            for token, pos in pos_tags:
                if (pos in important_pos and
                    token.lower() not in self.stop_words and
                    token.isalpha() and
                    len(token) > 2):
                    lemma = self.lemmatizer.lemmatize(token.lower())
                    if lemma and len(lemma) > 2:
                        keywords.append(lemma)
        
        except Exception:
            # Fallback to simple filtering if POS tagging fails
            keywords = [
                self.lemmatizer.lemmatize(token.lower())
                for token in tokens
                if (token.lower() not in self.stop_words and
                    token.isalpha() and
                    len(token) > 2)
            ]
        
        # Count frequency and calculate scores
        keyword_counts = Counter(keywords)
        total_keywords = len(keywords) if keywords else 1
        
        keyword_scores = []
        for keyword, count in keyword_counts.most_common():
            if count >= 1:  # Minimum frequency
                score = count / total_keywords
                keyword_scores.append((keyword, score))
        
        return keyword_scores[:max_keywords]
    
    def calculate_keyword_match_score(
        self,
        resume_text: str,
        job_description: str
    ) -> Dict[str, Any]:
        """Calculate how well resume keywords match job description.
        
        Args:
            resume_text: Resume content as text
            job_description: Job description text
            
        Returns:
            Match analysis with score and details
        """
        self._ensure_initialized()
        
        try:
            # Extract keywords from both texts
            resume_keywords = dict(self.extract_keywords_from_text(resume_text, max_keywords=50))
            job_keywords = dict(self.extract_keywords_from_text(job_description, max_keywords=50))
            
            # Find matching keywords
            resume_keyword_set = set(resume_keywords.keys())
            job_keyword_set = set(job_keywords.keys())
            
            matching_keywords = resume_keyword_set.intersection(job_keyword_set)
            missing_keywords = job_keyword_set - resume_keyword_set
            
            # Calculate match score
            if len(job_keyword_set) > 0:
                match_score = len(matching_keywords) / len(job_keyword_set) * 100
            else:
                match_score = 0
            
            # Calculate weighted score based on keyword importance
            weighted_score = 0
            total_weight = 0
            
            for keyword in job_keyword_set:
                weight = job_keywords[keyword]
                total_weight += weight
                if keyword in matching_keywords:
                    weighted_score += weight
            
            if total_weight > 0:
                weighted_match_score = (weighted_score / total_weight) * 100
            else:
                weighted_match_score = 0
            
            return {
                "match_score": round(match_score, 2),
                "weighted_match_score": round(weighted_match_score, 2),
                "matching_keywords": list(matching_keywords),
                "missing_keywords": list(missing_keywords)[:10],  # Top 10 missing
                "total_job_keywords": len(job_keyword_set),
                "total_resume_keywords": len(resume_keyword_set),
                "keyword_overlap": len(matching_keywords)
            }
            
        except Exception as e:
            self.logger.error(f"Keyword match calculation failed: {e}")
            return {
                "match_score": 0,
                "weighted_match_score": 0,
                "matching_keywords": [],
                "missing_keywords": [],
                "error": str(e)
            }
    
    def suggest_resume_improvements(
        self,
        resume_content: Dict[str, Any],
        job_description: str
    ) -> Dict[str, Any]:
        """Suggest improvements to resume based on job description analysis.
        
        Args:
            resume_content: Resume content dictionary
            job_description: Target job description
            
        Returns:
            Improvement suggestions and analysis
        """
        self._ensure_initialized()
        
        try:
            # Convert resume to text for analysis
            resume_text = self._resume_dict_to_text(resume_content)
            
            # Analyze keyword matching
            keyword_analysis = self.calculate_keyword_match_score(resume_text, job_description)
            
            # Validate ATS compliance
            ats_analysis = ATSOptimizer.validate_ats_compliance(resume_content)
            
            # Extract job requirements
            job_keywords = self.extract_keywords_from_text(job_description, max_keywords=30)
            
            # Generate suggestions
            suggestions = []
            
            # Keyword-based suggestions
            if keyword_analysis["match_score"] < 60:
                suggestions.append({
                    "type": "keywords",
                    "priority": "high",
                    "message": "Low keyword match with job description",
                    "action": f"Add these missing keywords: {', '.join(keyword_analysis['missing_keywords'][:5])}"
                })
            
            # ATS compliance suggestions
            if not ats_analysis["compliant"]:
                suggestions.extend([
                    {
                        "type": "ats_compliance",
                        "priority": "medium",
                        "message": issue,
                        "action": suggestion
                    }
                    for issue, suggestion in zip(ats_analysis["issues"], ats_analysis["suggestions"])
                ])
            
            # Content structure suggestions
            if "summary" not in resume_content or not resume_content.get("summary"):
                suggestions.append({
                    "type": "structure",
                    "priority": "high",
                    "message": "Missing professional summary",
                    "action": "Add a 2-3 sentence professional summary highlighting your key qualifications"
                })
            
            # Skills section suggestions
            if len(keyword_analysis["missing_keywords"]) > 5:
                suggestions.append({
                    "type": "skills",
                    "priority": "medium",
                    "message": "Skills section could be enhanced",
                    "action": f"Consider adding these relevant skills: {', '.join(keyword_analysis['missing_keywords'][:3])}"
                })
            
            return {
                "overall_score": (keyword_analysis["weighted_match_score"] + ats_analysis["ats_score"]) / 2,
                "keyword_analysis": keyword_analysis,
                "ats_analysis": ats_analysis,
                "suggestions": suggestions,
                "top_job_keywords": [kw for kw, _ in job_keywords[:10]],
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Resume improvement analysis failed: {e}")
            return {
                "overall_score": 0,
                "error": str(e),
                "suggestions": []
            }
    
    def _resume_dict_to_text(self, resume_content: Dict[str, Any]) -> str:
        """Convert resume dictionary to plain text for analysis.
        
        Args:
            resume_content: Resume content dictionary
            
        Returns:
            Resume as plain text
        """
        text_parts = []
        
        # Add summary
        if "summary" in resume_content:
            text_parts.append(resume_content["summary"])
        
        # Add experience
        if "experience" in resume_content and isinstance(resume_content["experience"], list):
            for job in resume_content["experience"]:
                if isinstance(job, dict):
                    if "title" in job:
                        text_parts.append(job["title"])
                    if "company" in job:
                        text_parts.append(job["company"])
                    if "description" in job:
                        text_parts.append(job["description"])
        
        # Add skills
        if "skills" in resume_content:
            skills = resume_content["skills"]
            if isinstance(skills, list):
                text_parts.extend(skills)
            elif isinstance(skills, str):
                text_parts.append(skills)
        
        # Add education
        if "education" in resume_content and isinstance(resume_content["education"], list):
            for edu in resume_content["education"]:
                if isinstance(edu, dict):
                    if "degree" in edu:
                        text_parts.append(edu["degree"])
                    if "institution" in edu:
                        text_parts.append(edu["institution"])
        
        return " ".join(text_parts)
    
    def extract_technical_skills(self, text: str) -> List[str]:
        """Extract technical skills and technologies from text.
        
        Args:
            text: Input text (job description or resume)
            
        Returns:
            List of technical skills found
        """
        # Common technical skills and technologies
        tech_skills = {
            # Programming languages
            'python', 'javascript', 'java', 'c++', 'c#', 'php', 'ruby', 'go', 'rust', 'swift',
            'kotlin', 'scala', 'r', 'matlab', 'sql', 'typescript', 'html', 'css',
            
            # Frameworks and libraries
            'react', 'angular', 'vue', 'django', 'flask', 'fastapi', 'spring', 'express',
            'nodejs', 'laravel', 'rails', 'bootstrap', 'jquery', 'tensorflow', 'pytorch',
            'scikit-learn', 'pandas', 'numpy', 'matplotlib',
            
            # Databases
            'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'sqlite', 'oracle',
            'cassandra', 'dynamodb',
            
            # Cloud and DevOps
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'gitlab', 'github',
            'terraform', 'ansible', 'chef', 'puppet', 'vagrant',
            
            # Tools and technologies
            'git', 'linux', 'unix', 'bash', 'powershell', 'vim', 'vscode', 'intellij',
            'eclipse', 'postman', 'swagger', 'jira', 'confluence', 'slack',
            
            # Methodologies
            'agile', 'scrum', 'kanban', 'devops', 'ci/cd', 'tdd', 'bdd', 'microservices',
            'rest', 'graphql', 'soap', 'api', 'json', 'xml'
        }
        
        # Clean and tokenize text
        cleaned_text = self._clean_text(text)
        words = cleaned_text.split()
        
        # Find technical skills
        found_skills = []
        for word in words:
            # Direct match
            if word in tech_skills:
                found_skills.append(word)
            
            # Handle compound terms like "ci/cd"
            if '/' in word:
                compound = word.replace('/', '')
                if compound in tech_skills:
                    found_skills.append(word)
        
        # Remove duplicates while preserving order
        unique_skills = []
        seen = set()
        for skill in found_skills:
            if skill not in seen:
                unique_skills.append(skill)
                seen.add(skill)
        
        return unique_skills
    
    def analyze_job_requirements(self, job_description: str) -> Dict[str, Any]:
        """Analyze job description to extract structured requirements.
        
        Args:
            job_description: Job description text
            
        Returns:
            Structured analysis of job requirements
        """
        self._ensure_initialized()
        
        try:
            # Extract keywords
            keywords = self.extract_keywords_from_text(job_description, max_keywords=30)
            
            # Extract technical skills
            tech_skills = self.extract_technical_skills(job_description)
            
            # Analyze experience requirements
            experience_patterns = [
                r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
                r'(\d+)\s*to\s*(\d+)\s*(?:years?|yrs?)',
                r'minimum\s*(\d+)\s*(?:years?|yrs?)',
                r'at\s*least\s*(\d+)\s*(?:years?|yrs?)'
            ]
            
            experience_requirements = []
            for pattern in experience_patterns:
                matches = re.findall(pattern, job_description.lower())
                for match in matches:
                    if isinstance(match, tuple):
                        experience_requirements.extend([int(x) for x in match if x.isdigit()])
                    else:
                        experience_requirements.append(int(match))
            
            # Determine experience level
            if experience_requirements:
                min_exp = min(experience_requirements)
                max_exp = max(experience_requirements)
                if min_exp <= 2:
                    exp_level = "junior"
                elif min_exp <= 5:
                    exp_level = "mid"
                else:
                    exp_level = "senior"
            else:
                exp_level = "not_specified"
            
            # Extract education requirements
            education_keywords = ['bachelor', 'master', 'phd', 'degree', 'diploma', 'certification']
            education_found = []
            for keyword in education_keywords:
                if keyword in job_description.lower():
                    education_found.append(keyword)
            
            # Categorize keywords
            soft_skills = []
            hard_skills = []
            
            for keyword, score in keywords:
                if keyword in tech_skills:
                    hard_skills.append((keyword, score))
                elif keyword in ['communication', 'leadership', 'teamwork', 'problem-solving', 'analytical']:
                    soft_skills.append((keyword, score))
            
            return {
                "keywords": dict(keywords),
                "technical_skills": tech_skills,
                "experience_requirements": {
                    "years": experience_requirements,
                    "level": exp_level,
                    "min_years": min(experience_requirements) if experience_requirements else 0,
                    "max_years": max(experience_requirements) if experience_requirements else 0
                },
                "education_requirements": education_found,
                "hard_skills": dict(hard_skills),
                "soft_skills": dict(soft_skills),
                "total_keywords": len(keywords),
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Job requirements analysis failed: {e}")
            return {
                "error": str(e),
                "keywords": {},
                "technical_skills": [],
                "experience_requirements": {"level": "unknown", "years": []},
                "education_requirements": []
            }
    
    def optimize_resume_content(
        self,
        resume_content: Dict[str, Any],
        job_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize resume content based on job requirements analysis.
        
        Args:
            resume_content: Original resume content
            job_requirements: Job requirements from analyze_job_requirements
            
        Returns:
            Optimized resume content with changes tracked
        """
        optimized = resume_content.copy()
        changes_made = []
        
        # Get job technical skills and keywords
        job_tech_skills = set(job_requirements.get("technical_skills", []))
        job_keywords = set(job_requirements.get("keywords", {}).keys())
        
        # Optimize skills section
        if "skills" in optimized:
            current_skills = set()
            if isinstance(optimized["skills"], list):
                current_skills = set([skill.lower() for skill in optimized["skills"]])
            elif isinstance(optimized["skills"], str):
                current_skills = set([skill.strip().lower() for skill in optimized["skills"].split(",")])
            
            # Add missing technical skills that the user likely has
            resume_text = self._resume_dict_to_text(resume_content).lower()
            skills_to_add = []
            
            for tech_skill in job_tech_skills:
                if tech_skill not in current_skills and tech_skill in resume_text:
                    skills_to_add.append(tech_skill.title())
            
            if skills_to_add:
                if isinstance(optimized["skills"], list):
                    optimized["skills"].extend(skills_to_add)
                else:
                    optimized["skills"] += ", " + ", ".join(skills_to_add)
                changes_made.append(f"Added technical skills: {', '.join(skills_to_add)}")
        
        # Optimize summary section
        if "summary" in optimized and job_keywords:
            summary = optimized["summary"]
            summary_lower = summary.lower()
            
            # Add important keywords to summary if not present
            keywords_to_add = []
            for keyword in list(job_keywords)[:5]:  # Top 5 keywords
                if keyword not in summary_lower and len(keyword) > 3:
                    keywords_to_add.append(keyword)
            
            if keywords_to_add:
                # Add keywords naturally to the summary
                additional_text = f" Experienced in {', '.join(keywords_to_add)}."
                optimized["summary"] = summary + additional_text
                changes_made.append(f"Enhanced summary with keywords: {', '.join(keywords_to_add)}")
        
        # Apply ATS formatting
        optimized = ATSOptimizer.optimize_formatting(optimized)
        changes_made.append("Applied ATS-friendly formatting")
        
        return {
            "optimized_content": optimized,
            "changes_made": changes_made,
            "optimization_score": len(changes_made) * 10,  # Simple scoring
            "optimized_at": datetime.utcnow().isoformat()
        }


# Global service instance
nlp_service = NLPService()