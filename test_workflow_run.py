import asyncio
from httpx import AsyncClient

async def test_workflow():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # We need an auth token
        login_res = await client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "password123"})
        if login_res.status_code != 200:
            # Register user
            await client.post("/api/v1/auth/register", json={"email": "test@example.com", "password": "password123"})
            login_res = await client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "password123"})
            
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. CREATE PROFILE
        profile_data = {
            "identity": {"first_name": "John", "last_name": "Doe", "email": "test@example.com", "phone": "123456789"},
            "location": {"country": "Saudi Arabia", "city": "Riyadh", "preferred_locations": [], "willing_to_relocate": False, "remote_preference": "hybrid"},
            "employment": {"current_title": "Software Engineer", "years_of_experience": 5, "notice_period": "30 days"},
            "work_authorization": {"nationality": "Saudi", "residency_country": "Saudi Arabia", "work_authorization_status": "Citizen", "iqama_transferable": False},
            "education": [{"degree": "BSc Computer Science", "institution": "KSU", "field_of_study": "CS", "graduation_year": "2020"}],
            "experience": [{"company": "TechCorp", "title": "Senior Engineer", "start_date": "2021", "end_date": "Present", "description": "Built cool stuff.", "achievements": [], "technologies": ["Python", "React"]}],
            "skills": [{"name": "Python", "proficiency": "expert", "years": 5, "evidence": ""}],
            "projects": [],
            "certifications": [],
            "preferences": {"target_roles": [], "target_countries": [], "target_cities": [], "minimum_salary": 0, "salary_currency": "USD", "employment_types": [], "excluded_companies": []}
        }
        res = await client.post("/api/v1/candidate-profile", json=profile_data, headers=headers)
        print("Create Profile:", res.status_code)
        
        # 2. ANALYZE JOB
        job_res = await client.post("/api/v1/workflow/jobs/analyze", json={
            "job_description": "We need a Python engineer in Riyadh.",
            "title": "Python Engineer",
            "company": "TestCorp"
        }, headers=headers)
        print("Analyze Job:", job_res.status_code)
        job_id = job_res.json()["id"]
        # Mock LLM data since the API key provided in .env is invalid
        tailored_data = {
            "summary": "Experienced Python Engineer ready to build.",
            "experiences": [
                {
                    "job_title": "Python Engineer",
                    "company_name": "TechCorp",
                    "start_date": "2021",
                    "end_date": "Present",
                    "description": "Built cool stuff.",
                    "achievements": ["Increased performance by 20%"]
                }
            ],
            "skills": ["Python", "React", "FastAPI"]
        }
        
        # 5/6. GENERATE PDF & CREATE READY APPLICATION
        app_res = await client.post(f"/api/v1/workflow/jobs/{job_id}/prepare-application", json=tailored_data, headers=headers)
        print("Prepare App:", app_res.status_code)
        print(app_res.json())

if __name__ == "__main__":
    asyncio.run(test_workflow())
