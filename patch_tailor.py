import re

with open("backend/app/services/workflow_service.py", "r", encoding="utf-8") as f:
    content = f.read()

pattern = r"        tailored_data = await self\.llm_client\.complete_with_structured_output\([\s\S]*?purpose=\"resume_tailor\"\s*\)\s*return tailored_data"

replacement = """        try:
            tailored_data = await self.llm_client.complete_with_structured_output(
                prompt=prompt,
                system_prompt=system_prompt,
                output_schema=TailoredResumeData,
                purpose="resume_tailor"
            )
            return tailored_data
        except Exception as e:
            import logging
            logging.error(f"Resume tailor failed: {e}")
            from app.schemas.resume import TailoredResumeData, TailoredExperience
            
            # Deterministic fallback mapping
            exp = []
            for e in candidate_model.experience:
                exp.append(TailoredExperience(
                    id=e.get("id", "fallback_exp"),
                    title=e.get("title", ""),
                    company=e.get("company", ""),
                    date_range=e.get("date_range", ""),
                    bullets=e.get("bullets", [])
                ))
            
            return TailoredResumeData(
                professional_summary=candidate_model.identity.get("professional_summary", ""),
                experience=exp,
                skills=candidate_model.skills
            )"""

content = re.sub(pattern, replacement, content)

with open("backend/app/services/workflow_service.py", "w", encoding="utf-8") as f:
    f.write(content)
