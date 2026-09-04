"""Manual Opportunity Provider for unstructured text ingestion."""

import json
from typing import Any, Dict
from datetime import datetime, UTC

from app.core.job_discovery.opportunity_source import UserFedOpportunitySource
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.core.llm.prompts.opportunity_extraction import OPPORTUNITY_EXTRACTION_PROMPT

class ManualProvider(UserFedOpportunitySource):
    def name(self) -> str:
        return "manual"
        
    async def health_check(self) -> bool:
        return True

    async def ingest(self, input_text: str, **kwargs) -> Dict[str, Any]:
        """Use LLM to extract JSON from unstructured text."""
        client = LLMTaskRouter(LLMClient())
        response = await client.complete(
            task=LLMTask.JOB_NORMALIZATION,
            system_prompt=OPPORTUNITY_EXTRACTION_PROMPT,
            prompt=f"Raw text:\n\n{input_text}",
            temperature=0.0
        )
        try:
            # Clean up potential markdown formatting if the LLM ignores instructions
            cleaned = response.content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                
            extracted = json.loads(cleaned.strip())
        except Exception:
            # Fallback if parsing completely fails
            extracted = {
                "title": "Unknown Job Opportunity",
                "company": "Unknown",
                "description": input_text,
            }
            
        # Retain original text and timestamp for provenance
        extracted["_raw_text"] = input_text
        extracted["_received_at"] = datetime.now(UTC).isoformat()
        
        # Apply explicit overrides if provided
        if kwargs.get("title_override"):
            extracted["title"] = kwargs["title_override"]
        if kwargs.get("company_override"):
            extracted["company"] = kwargs["company_override"]
            
        return extracted

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize the extracted dictionary into canonical schema fields."""
        return {
            "title": raw_data.get("title") or "Unknown Position",
            "company": raw_data.get("company") or "Confidential",
            "description": raw_data.get("description") or "",
            "location": raw_data.get("location") or "",
            "requirements": raw_data.get("requirements") or "",
            "salary_range": raw_data.get("salary_range"),
            "remote": raw_data.get("remote") or False,
            "employment_type": raw_data.get("employment_type"),
            "url": raw_data.get("application_url") or "", # Fallback URL
            "application_url": raw_data.get("application_url"),
            # We also pass through the raw data so the RouteResolver can use instructions/email
            "raw_data": raw_data,
            "raw_text": raw_data.get("_raw_text", ""),
            "received_at": datetime.fromisoformat(raw_data.get("_received_at")) if raw_data.get("_received_at") else datetime.now(UTC)
        }

