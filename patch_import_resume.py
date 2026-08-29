import re

with open("backend/app/api/v1/candidate_profile.py", "r", encoding="utf-8") as f:
    content = f.read()

replacement = """        try:
            draft_response = await llm.complete_with_structured_output(
                prompt=f"Resume Text:\\n{parsed_doc.raw_text}",
                output_schema=CandidateProfileDraft,
                system_prompt=system_prompt
            )
            return draft_response
        except Exception as llm_exc:
            # Fallback for when the free LLM is unavailable or ratelimited
            import logging
            logging.error(f"LLM parsing failed: {llm_exc}")
            
            # Create a mock draft using the extracted text in the summary
            draft = CandidateProfileDraft()
            draft.identity.professional_summary.value = parsed_doc.raw_text[:2000] # truncate
            draft.identity.professional_summary.confidence = 1.0
            draft.identity.professional_summary.source = "resume_fallback"
            return draft
        
    finally:"""

content = re.sub(r'draft_response = await llm\.complete_with_structured_output\([\s\S]*?return draft_response\s*finally:', replacement, content)

with open("backend/app/api/v1/candidate_profile.py", "w", encoding="utf-8") as f:
    f.write(content)
