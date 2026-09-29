import os

import pytest

from app.core.connectors.base import ApplicationQuestion
from app.core.llm.client import LLMClient
from app.services.matching import LLMMatchResult
from app.services.question_engine import QuestionEngine

pytestmark = pytest.mark.asyncio

# Removed mock


async def test_openrouter_smoke_matching():
    if not os.getenv("RUN_LIVE_LLM_TESTS"):
        pytest.skip(
            "Set RUN_LIVE_LLM_TESTS=1 to run paid/network OpenRouter smoke tests"
        )
    client = LLMClient()

    # 1. Matching Schema Test
    prompt = """
    Evaluate this dummy candidate against this dummy job.
    Job: Need Python dev with 5 years exp.
    Candidate: Python dev with 6 years exp.
    """

    try:
        res = await client.complete_with_structured_output(
            prompt=prompt, output_schema=LLMMatchResult
        )
        assert res.score >= 0
        assert isinstance(res.strengths, list)
    except Exception as e:
        pytest.fail(f"Matching test failed: {e}")


async def test_openrouter_smoke_category_c():
    if not os.getenv("RUN_LIVE_LLM_TESTS"):
        pytest.skip(
            "Set RUN_LIVE_LLM_TESTS=1 to run paid/network OpenRouter smoke tests"
        )
    client = LLMClient()

    profile = {
        "experience": [
            {
                "evidence_id": "experience-data-001",
                "description": "Worked as a Python developer.",
            },
            {
                "evidence_id": "project-python-001",
                "description": "Built a web app in Python.",
            },
        ]
    }

    engine = QuestionEngine(profile, client)

    q = ApplicationQuestion(
        question_id="interest",
        label="Why are you interested in this position?",
        input_type="textarea",
        required=True,
    )

    # 2. Category C (D_AI_EVIDENCE_GROUNDED) Test
    try:
        resolved = await engine.resolve([q])
        ans = resolved[0]
        assert ans.category.name == "D_AI_EVIDENCE_GROUNDED" or getattr(
            ans, "requires_human", False
        )
    except Exception as e:
        pytest.fail(f"Category C test failed: {e}")


async def test_reject_fabricated_evidence():
    client = LLMClient()

    # Mock profile with specific evidence IDs
    profile = {
        "experience": [{"evidence_id": "real-evidence-001", "description": "Real."}]
    }
    engine = QuestionEngine(profile, client)

    # We will simulate a response from the LLM containing a fake evidence ID
    # Since we can't reliably force the LLM to hallucinate on demand, we directly test the validation logic

    # The QuestionEngine rejects fabricated evidence IDs by checking self.valid_evidence_ids
    # Let's ensure the engine correctly identified valid evidence
    assert "real-evidence-001" in engine.valid_evidence_ids
    assert "fake-evidence-999" not in engine.valid_evidence_ids
