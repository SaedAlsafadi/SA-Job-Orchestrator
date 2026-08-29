import re

with open("backend/app/api/v1/candidate_profile.py", "r", encoding="utf-8") as f:
    content = f.read()

pattern = r"@router\.post\(\"/import-resume\", response_model=CandidateProfileDraft\)\s*async def import_resume\([\s\S]*?(?=@router|$)"

replacement = r"""@router.post("/import-resume", response_model=CandidateProfileDraft)
async def import_resume(
    user: CurrentUser,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db)
):
    import shutil
    
    # Save uploaded file to temp file for parser
    ext = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = Path(temp_file.name)
        
    try:
        # Parse document
        parser = DocumentParser()
        parsed_doc = await parser.parse(temp_path)
        
        # LLM Extraction
        llm = LLMClient()
        system_prompt = \"\"\"
        You are an expert HR data extractor. Extract the candidate's professional profile from the provided resume text into a highly structured draft format.
        
        CRITICAL RULES:
        1. NEVER guess or infer information (like dates, nationality, visa status, or unsupported skills).
        2. Unknown values must be left null.
        3. Assign a confidence score (0.0 to 1.0) to every extracted value.
        4. "source" must be "resume" for every value.
        5. For multi-item fields (like skills, languages), extract each entry individually.
        \"\"\"
        
        try:
            draft_response = await llm.complete_with_structured_output(
                prompt=f"Resume Text:\\n{parsed_doc.raw_text}",
                output_schema=CandidateProfileDraft,
                system_prompt=system_prompt
            )
            return draft_response
        except Exception as llm_exc:
            import logging
            logging.error(f"LLM parsing failed: {llm_exc}")
            
            # Create a mock draft using the extracted text in the summary
            draft = CandidateProfileDraft()
            draft.identity.professional_summary.value = parsed_doc.raw_text[:2000] # truncate
            draft.identity.professional_summary.confidence = 1.0
            draft.identity.professional_summary.source = "resume_fallback"
            return draft
            
    finally:
        if temp_path.exists():
            os.remove(temp_path)

"""

# Fix escaped triple quotes inside the raw string
replacement = replacement.replace('\\"\\"\\"', '"""')

content = re.sub(pattern, replacement, content)

with open("backend/app/api/v1/candidate_profile.py", "w", encoding="utf-8") as f:
    f.write(content)
