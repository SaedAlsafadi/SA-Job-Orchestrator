import pytest
from app.core.job_discovery.providers.bayt_provider import BaytDiscoveryProvider

MOCK_BAYT_HTML = """
<!DOCTYPE html>
<html>
<body>
    <ul class="list-jobs">
        <li class="has-pointer-d job-item" data-job-id="1234567">
            <h2 class="jb-title">
                <a href="/en/saudi-arabia/jobs/senior-ai-engineer-1234567/">Senior AI Engineer</a>
            </h2>
            <div class="jb-company">Tech Innovators LLC</div>
            <div class="jb-loc">Riyadh, Saudi Arabia</div>
            <div class="jb-descr">We are looking for a Senior AI Engineer with experience in PyTorch and LLMs.</div>
        </li>
        <li class="has-pointer-d job-item" data-job-id="7654321">
            <h2 class="jb-title">
                <a href="/en/saudi-arabia/jobs/data-scientist-7654321/">Data Scientist</a>
            </h2>
            <div class="jb-company">GCC Analytics</div>
            <div class="jb-loc">Jeddah, Saudi Arabia</div>
            <div class="jb-descr">Join our data science team. Saudi Nationals only.</div>
        </li>
    </ul>
</body>
</html>
"""

@pytest.fixture
def bayt_provider():
    return BaytDiscoveryProvider()

def test_bayt_provider_capabilities(bayt_provider):
    caps = bayt_provider.capabilities()
    assert caps.global_search is True
    assert caps.direct_url is True

def test_bayt_parse_search_page(bayt_provider):
    base_url = "https://www.bayt.com/en/saudi-arabia/jobs/search/"
    results = bayt_provider._parse_search_page(MOCK_BAYT_HTML, base_url)
    
    assert len(results) == 2
    
    job1 = results[0]
    assert job1["title"] == "Senior AI Engineer"
    assert job1["company"] == "Tech Innovators LLC"
    assert job1["location"] == "Riyadh, Saudi Arabia"
    assert job1["url"] == "https://www.bayt.com/en/saudi-arabia/jobs/senior-ai-engineer-1234567/"
    assert job1["platform_job_id"] == "1234567"
    assert "PyTorch" in job1["description"]

def test_bayt_normalization(bayt_provider):
    raw_data = {
        "title": "Senior AI Engineer",
        "company": "Tech Innovators LLC",
        "location": "Riyadh, Saudi Arabia",
        "url": "https://www.bayt.com/en/saudi-arabia/jobs/senior-ai-engineer-1234567/",
        "platform_job_id": "1234567",
        "description": "We are looking for a Senior AI Engineer with experience in PyTorch and LLMs."
    }
    
    job = bayt_provider.normalize(raw_data)
    
    assert job["title"] == "Senior AI Engineer"
    assert job["company"] == "Tech Innovators LLC"
    assert job["platform"] == "bayt"
    assert job["source_type"] == "bayt"
    assert "Tech Innovators LLC" in job["raw_text"]
    assert "PyTorch" in job["raw_text"]
