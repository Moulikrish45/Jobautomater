"""Test free job search."""

import asyncio
from app.utcp.free_client import FreeJobClient
from collections import Counter


async def main():
    client = FreeJobClient()
    
    print("🔍 Searching 8 job sources (LinkedIn, Indeed, Glassdoor + 5 APIs)...\n")
    jobs = await client.search_all(["python", "developer"], "remote")
    
    # Count by source
    sources = Counter(job['source'] for job in jobs)
    
    print(f"✅ Found {len(jobs)} total jobs:\n")
    for source, count in sources.items():
        print(f"  {source.capitalize()}: {count} jobs")
    
    print(f"\n📋 Sample jobs:")
    for job in jobs[:15]:
        print(f"  • {job['title']} at {job['company']} [{job['source']}]")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
