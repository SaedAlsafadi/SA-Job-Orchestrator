import pytest
import asyncio
from app.core.job_discovery.providers.bayt_provider import BaytDiscoveryProvider

# Disabled by default. Run with pytest tests/test_bayt_real.py -s to test manually.
@pytest.mark.skip(reason="Manual real discovery test disabled by default")
@pytest.mark.asyncio
async def test_bayt_real_discovery():
    provider = BaytDiscoveryProvider()
    
    # 1. Perform one bounded real Bayt search
    results = await provider.search(query="software engineer", filters={"location": "Riyadh"})
    
    print(f"\n--- Found {len(results)} jobs on Bayt ---")
    
    # 2. Retrieve public job listings
    for idx, r in enumerate(results[:5]):
        # 3. Normalize several jobs
        job = provider.normalize(r)
        
        # 4. Print their source URLs
        print(f"\n[Job {idx+1}] {job['title']} at {job['company']}")
        print(f"Location: {job['location']}")
        print(f"URL: {job['url']}")
        
        # 5. Report extraction quality
        assert job['title']
        assert job['url']
        assert job['source_type'] == "bayt"
        
    if not results:
        print("No results returned. The provider might have been blocked by Cloudflare (HTTP 403).")
