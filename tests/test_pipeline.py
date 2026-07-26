"""Integration test for the full LangGraph pipeline."""

import pytest

from agent.pipeline import run_pipeline
from tests.conftest import SAMPLE_RESUME, SAMPLE_JD


class TestPipeline:
    def test_full_pipeline_returns_all_keys(self):
        result = run_pipeline(raw_resume=SAMPLE_RESUME, raw_jd=SAMPLE_JD)
        for key in ("resume_data", "jd_data", "gaps", "cover_letter", "interview_questions"):
            assert key in result, f"Missing key: {key}"
        assert isinstance(result["cached"], bool)

    def test_gaps_trigger_tailored_bullets(self):
        result = run_pipeline(raw_resume=SAMPLE_RESUME, raw_jd=SAMPLE_JD)
        if result.get("gaps"):
            assert result.get("tailored_bullets") is not None
