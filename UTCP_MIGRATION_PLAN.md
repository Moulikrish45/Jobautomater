# UTCP Migration Plan for Job Application Automation

## Why UTCP for Startups?

### Current Architecture Issues
1. **Fragile Web Scraping**: Portal UI changes break scrapers constantly
2. **Rate Limiting**: Getting blocked by job portals
3. **No Official APIs**: LinkedIn/Indeed APIs require enterprise partnerships
4. **Complex MCP Setup**: Overhead for agent coordination

### UTCP Benefits
1. **Direct Tool Integration**: Connect AI agents to APIs/CLIs without wrapper servers
2. **Standardized Protocol**: Universal interface for all tools
3. **Reduced Complexity**: No need for MCP server infrastructure
4. **Faster Development**: Plug-and-play tool integration
5. **Cost Effective**: Use existing APIs directly

## Migration Strategy

### Phase 1: Replace Web Scrapers with API Tools (Week 1-2)

#### Option A: Use Job Aggregator APIs
```yaml
Tools to Integrate via UTCP:
  - Adzuna API (free tier: 1000 calls/month)
  - JSearch API (RapidAPI - affordable)
  - Reed API (UK jobs)
  - Remotive API (remote jobs)
  - GitHub Jobs API (tech jobs)
```

#### Option B: Use Official APIs (if available)
```yaml
LinkedIn:
  - LinkedIn Jobs API (requires partnership)
  - Alternative: LinkedIn Voyager API (unofficial)

Indeed:
  - Indeed Publisher API (requires approval)
  - Alternative: Indeed RSS feeds

Naukri:
  - No official API
  - Alternative: Use Adzuna for Indian market
```

### Phase 2: UTCP Tool Definitions (Week 2)

```typescript
// utcp-tools.json
{
  "tools": [
    {
      "name": "search_jobs_adzuna",
      "description": "Search jobs using Adzuna API",
      "protocol": "utcp",
      "endpoint": "https://api.adzuna.com/v1/api/jobs/{country}/search/1",
      "method": "GET",
      "auth": {
        "type": "query_params",
        "params": ["app_id", "app_key"]
      },
      "parameters": {
        "what": "string",
        "where": "string",
        "results_per_page": "number",
        "max_days_old": "number"
      }
    },
    {
      "name": "search_jobs_jsearch",
      "description": "Search jobs using JSearch API",
      "protocol": "utcp",
      "endpoint": "https://jsearch.p.rapidapi.com/search",
      "method": "GET",
      "auth": {
        "type": "header",
        "header": "X-RapidAPI-Key"
      },
      "parameters": {
        "query": "string",
        "page": "number",
        "num_pages": "number",
        "date_posted": "string"
      }
    },
    {
      "name": "parse_resume_affinda",
      "description": "Parse resume using Affinda API",
      "protocol": "utcp",
      "endpoint": "https://api.affinda.com/v3/resumes",
      "method": "POST",
      "auth": {
        "type": "bearer"
      }
    },
    {
      "name": "optimize_resume_huggingface",
      "description": "Optimize resume using HuggingFace free API",
      "protocol": "utcp",
      "endpoint": "https://api-inference.huggingface.co/models/yanekyuk/bert-uncased-keyword-extractor",
      "method": "POST"
    }
  ]
}
```

### Phase 3: Backend Refactoring (Week 3)

**Remove:**
- `app/mcp/scrapers/` (all scraper files)
- `app/mcp/base_agent.py` (MCP agent base)
- Complex MCP server setup

**Add:**
```python
# app/utcp/client.py
from utcp import UTCPClient

class JobSearchUTCP:
    def __init__(self):
        self.client = UTCPClient()
        self.client.load_tools("utcp-tools.json")
    
    async def search_jobs(self, keywords: list, location: str):
        # Direct API call via UTCP
        results = await self.client.call_tool(
            "search_jobs_adzuna",
            what=" ".join(keywords),
            where=location,
            results_per_page=50
        )
        return results
```

### Phase 4: Cost Optimization (Week 4)

#### Free/Affordable APIs
```yaml
Job Search:
  - Adzuna: 1000 calls/month free
  - JSearch: $10/month for 1000 calls
  - Remotive: Free for remote jobs
  - GitHub Jobs: Free (deprecated but alternatives exist)

Resume Parsing:
  - Affinda: 100 resumes/month free
  - Resume Parser API: $29/month

AI/LLM:
  - Ollama: Free (local)
  - OpenAI: Pay-as-you-go
  - Anthropic Claude: Pay-as-you-go
```

#### Estimated Monthly Costs
```
Startup (100 users):
  - Job Search API: $50/month
  - Resume Parsing: $29/month
  - AI (Ollama local): $0
  - Infrastructure: $20/month
  Total: ~$100/month

vs Current (Web Scraping):
  - Proxy services: $200/month
  - CAPTCHA solving: $100/month
  - Maintenance: High (constant fixes)
  Total: $300+ month + dev time
```

## Implementation Code

### 1. UTCP Client Setup

```python
# app/utcp/client.py
import httpx
import json
from typing import Dict, Any, List

class UTCPClient:
    def __init__(self, tools_config: str = "utcp-tools.json"):
        with open(tools_config) as f:
            self.tools = json.load(f)["tools"]
        self.client = httpx.AsyncClient()
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        tool = next((t for t in self.tools if t["name"] == tool_name), None)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")
        
        # Build request
        url = tool["endpoint"]
        method = tool["method"]
        
        # Handle auth
        headers = {}
        params = {}
        
        if tool["auth"]["type"] == "bearer":
            headers["Authorization"] = f"Bearer {self._get_api_key(tool_name)}"
        elif tool["auth"]["type"] == "header":
            headers[tool["auth"]["header"]] = self._get_api_key(tool_name)
        elif tool["auth"]["type"] == "query_params":
            for param in tool["auth"]["params"]:
                params[param] = self._get_api_key(f"{tool_name}_{param}")
        
        # Add parameters
        params.update(kwargs)
        
        # Make request
        if method == "GET":
            response = await self.client.get(url, params=params, headers=headers)
        elif method == "POST":
            response = await self.client.post(url, json=kwargs, headers=headers)
        
        return response.json()
    
    def _get_api_key(self, key_name: str) -> str:
        # Load from environment or config
        import os
        return os.getenv(key_name.upper())
```

### 2. Job Search Service with UTCP

```python
# app/services/job_search_utcp_service.py
from app.utcp.client import UTCPClient
from app.models.job import Job, JobPortal
from typing import List

class JobSearchUTCPService:
    def __init__(self):
        self.utcp = UTCPClient()
    
    async def search_jobs(
        self,
        keywords: List[str],
        location: str,
        max_results: int = 50
    ) -> List[Job]:
        # Use Adzuna API via UTCP
        results = await self.utcp.call_tool(
            "search_jobs_adzuna",
            what=" ".join(keywords),
            where=location,
            results_per_page=max_results
        )
        
        # Transform to Job model
        jobs = []
        for result in results.get("results", []):
            job = Job(
                external_id=result["id"],
                portal=JobPortal.ADZUNA,
                url=result["redirect_url"],
                title=result["title"],
                company={"name": result["company"]["display_name"]},
                location={"city": result["location"]["display_name"]},
                description=result["description"],
                salary=result.get("salary_min"),
                posted_date=result["created"]
            )
            jobs.append(job)
        
        return jobs
```

### 3. FastAPI Endpoint Update

```python
# app/api/jobs.py
from fastapi import APIRouter, Depends
from app.services.job_search_utcp_service import JobSearchUTCPService

router = APIRouter()

@router.post("/search")
async def search_jobs(
    keywords: List[str],
    location: str,
    service: JobSearchUTCPService = Depends()
):
    jobs = await service.search_jobs(keywords, location)
    return {"jobs": jobs, "count": len(jobs)}
```

## Migration Checklist

- [ ] Week 1: Research and sign up for job APIs (Adzuna, JSearch)
- [ ] Week 1: Create UTCP tool definitions
- [ ] Week 2: Implement UTCP client
- [ ] Week 2: Build job search service with UTCP
- [ ] Week 3: Update FastAPI endpoints
- [ ] Week 3: Remove old scraper code
- [ ] Week 4: Test end-to-end
- [ ] Week 4: Deploy and monitor

## Rollback Plan

Keep old scrapers in `app/mcp/scrapers_legacy/` for 1 month as fallback.

## Success Metrics

- **Reliability**: 99% uptime (vs 80% with scrapers)
- **Speed**: <2s response time (vs 10s+ with scraping)
- **Cost**: <$100/month (vs $300+)
- **Maintenance**: 1 hour/week (vs 10+ hours/week)

## Next Steps

1. **Immediate**: Sign up for Adzuna API (free tier)
2. **Day 1**: Create UTCP tool definitions
3. **Day 2**: Implement UTCP client
4. **Week 1**: Build parallel system with UTCP
5. **Week 2**: A/B test UTCP vs scrapers
6. **Week 3**: Full migration if successful
