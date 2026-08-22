import asyncio
from fastapi.testclient import TestClient
from app.main import app

def run_e2e():
    client = TestClient(app)
    
    # Authenticate or bypass?
    # TestClient doesn't automatically auth unless we inject token or override dependency.
    # We can override get_current_user
    from app.api.deps import get_current_user
    from app.models.user import User
    
    user = User(id="test-e2e-user", email="test@example.com")
    app.dependency_overrides[get_current_user] = lambda: user
    
    print("1. Uploading CV to create CandidateProfile...")
    with open("test_candidate_cv.pdf", "rb") as f:
        res = client.post("/api/v1/profile/import-resume", files={"file": ("test_candidate_cv.pdf", f, "application/pdf")})
    
    if res.status_code != 200:
        print("Upload failed:", res.status_code, res.text)
        return
        
    draft = res.json()
    print("Draft generated successfully. Verifying profile...")
    
    # Save/Verify
    res = client.post("/api/v1/profile/verify", json=draft)
    if res.status_code != 200:
        print("Verify failed:", res.status_code, res.text)
        return
        
    profile = res.json()
    print("Profile verified:", profile['identity']['first_name'])
    
    print("\n2. Seeding a Real Job (Workable Project Manager)...")
    job_payload = {
        "url": "https://apply.workable.com/baraka-investment/j/ADAA86DA9E/"
    }
    # Wait, do we have an endpoint to scrape/add a job?
    # /api/v1/jobs/discover maybe? Or we can use the DB directly for this setup.
