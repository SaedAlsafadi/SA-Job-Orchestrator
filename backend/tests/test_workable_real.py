import asyncio
import os
import argparse
import sys
from pathlib import Path
from pprint import pprint

project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from app.core.connectors.workable_app import WorkableApplicationConnector
from app.services.question_engine import QuestionEngine
from app.core.llm.client import LLMClient
from app.core.connectors.base import QuestionCategory
from playwright.async_api import async_playwright

async def run_smoke_test(url: str):
    print(f"=== Real Workable Smoke Test (V2 - Panel Detection) ===")
    print(f"URL: {url}")
    print("WARNING: This test operates on a LIVE employer application form.")
    print("SUBMISSION IS DISABLED BY DESIGN. We will only prepare and screenshot.")
    
    # 1. Create mock resume and profile
    os.makedirs("data/storage", exist_ok=True)
    resume_path = "data/storage/mock_resume_test.pdf"
    with open(resume_path, "w") as f:
        f.write("MOCK RESUME CONTENT")
        
    mock_profile = {
        "identity": {
            "first_name": "Test",
            "last_name": "Applicant",
            "email": "test@example.com",
            "phone": "+1234567890"
        },
        "experience": [
            {"evidence_id": "exp-123", "title": "Software Engineer", "company": "Tech Corp"}
        ],
        "education": [
            {"evidence_id": "edu-456", "degree": "BSc Computer Science", "institution": "State University"}
        ]
    }
        
    connector = WorkableApplicationConnector()
    engine = QuestionEngine(mock_profile, LLMClient())
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("\n>>> 1. Opening job page and clicking Apply Now...")
            await connector.open_application(url, page)
            print("Successfully reached form panel!")
            
            print("\n>>> 2. Inspecting form state...")
            questions = await connector.inspect_form(page)
            
            form_detected = len(questions) > 0 or await connector.detect_cv_presence(page)
            if not form_detected:
                raise ValueError("CRITICAL FAILURE: form_detected=False. Application panel was not opened or form was not detected.")
            
            print(f"Extracted {len(questions)} fields.")
            
            print("\n>>> 3. Resolving Questions & Identifying Prefilled...")
            resolved = await engine.resolve(questions)
            
            cat_counts = {"A":0, "B":0, "C":0, "D":0, "E":0, "F":0}
            prefilled_count = 0
            
            for q in resolved:
                if q.prefilled:
                    prefilled_count += 1
                
                cat_letter = str(q.category.value if q.category else 'None')[0:1]
                if cat_letter in cat_counts:
                    cat_counts[cat_letter] += 1
                    
                print(f"\nField: {q.label} (ID: {q.question_id})")
                print(f"Current Value: '{q.current_value}' (Prefilled: {q.prefilled})")
                print(f"Category: {q.category}")
                print(f"Requires Human: {q.requires_human}")
                if q.answer and not q.prefilled: print(f"AI/Deterministic Answer: {q.answer}")
                if q.evidence_ids: print(f"Evidence: {q.evidence_ids}")
                
            print(f"\nTotal Prefilled: {prefilled_count}")
            print("Category Distribution:", cat_counts)
            
            print("\n>>> 4. Processing CV State & Filling Unresolved Fields...")
            cv_present = await connector.detect_cv_presence(page)
            print(f"CV Present on platform: {cv_present}")
            
            for q in resolved:
                if q.prefilled or q.requires_human:
                    continue
                    
                if q.input_type == "file" and "resume" in q.question_id.lower():
                    if cv_present:
                        print(" -> Skipping CV upload to avoid overwriting existing platform CV.")
                    else:
                        print(" -> Uploading Resume...")
                        await connector.upload_resume(page, resume_path)
                elif q.answer:
                    print(f" -> Filling {q.label}...")
                    await connector.answer_question(page, q)
            
            print("\n>>> 5. Capturing State and Screenshot...")
            os.makedirs("data/storage/screenshots", exist_ok=True)
            screenshot_path = "data/storage/screenshots/smoke_test.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")
            
            state = await connector.capture_state(page)
            state["screenshot"] = screenshot_path
            state["cv_present"] = cv_present
            state["questions"] = [q.model_dump() for q in resolved]
            
            print("\n>>> 6. STOPPING BEFORE SUBMISSION. Test passed successfully.")
            
        except Exception as e:
            print(f"\n[FAIL] Smoke test failed: {e}")
            raise
        finally:
            await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real Workable Smoke Test (V2)")
    parser.add_argument("url", help="Public Workable Job URL")
    args = parser.parse_args()
    
    asyncio.run(run_smoke_test(args.url))
