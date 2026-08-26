"""Unit tests for agent node functions — no API key required."""

from unittest.mock import patch, MagicMock

import pytest

from agent.models import (
    ResumeData, JDData, GapAnalysis, Gap, RecruiterInsight,
    TailoredBullets, TailoredBullet, InterviewQuestions,
)
from agent.nodes import (
    parse_resume, analyze_jd, gap_analysis,
    tailor_resume, generate_cover_letter, generate_interview_qs,
    route_after_gap_analysis,
)


# ── Fixtures ────────────────────────────────────────────────

MOCK_RESUME_DATA = ResumeData(
    name="Jane Doe",
    skills=["Python", "FastAPI", "SQL"],
    experience=[],
    education=[],
    summary="Backend developer with 3 years experience.",
)

MOCK_JD_DATA = JDData(
    title="Backend Engineer",
    company="Acme Corp",
    requirements=[
        {"skill": "Python", "importance": "must-have"},
        {"skill": "Docker", "importance": "nice-to-have"},
    ],
    responsibilities=["Build APIs", "Write tests"],
    experience_years="2-4 years",
)

MOCK_GAP_ANALYSIS = GapAnalysis(
    gaps=[Gap(requirement="Docker", importance="nice-to-have", assessment="No Docker experience listed.")],
    strengths=["Python", "SQL"],
    overall_match_pct=80,
    candidate_score=7,
    recruiter_insights=RecruiterInsight(
        hiring_risks=["No containerization experience"],
        recommendation="Hire",
        justification="Strong Python skills offset the Docker gap which can be learned on the job.",
    ),
)

MOCK_TAILORED_BULLETS = TailoredBullets(
    bullets=[
        TailoredBullet(
            original="Built REST APIs with FastAPI",
            tailored="Built containerization-ready REST APIs with FastAPI, deployed via CI/CD pipelines",
            gap_addressed="Docker",
        )
    ]
)

MOCK_INTERVIEW_QS = InterviewQuestions(
    questions=[
        "Describe your experience with Python web frameworks.",
        "How do you approach containerizing a Python application?",
    ]
)


# ── Node Tests ──────────────────────────────────────────────

class TestParseResume:
    @patch("agent.nodes.structured_invoke", return_value=MOCK_RESUME_DATA)
    def test_returns_resume_data(self, mock_invoke):
        result = parse_resume({"raw_resume": "Jane Doe\nPython developer"})
        assert result["resume_data"]["name"] == "Jane Doe"
        assert "Python" in result["resume_data"]["skills"]
        mock_invoke.assert_called_once()

    @patch("agent.nodes.structured_invoke", return_value=MOCK_RESUME_DATA)
    def test_passes_resume_text_to_llm(self, mock_invoke):
        parse_resume({"raw_resume": "test content"})
        prompt = mock_invoke.call_args[0][1]
        assert "test content" in prompt


class TestAnalyzeJD:
    @patch("agent.nodes.structured_invoke", return_value=MOCK_JD_DATA)
    def test_returns_jd_data(self, mock_invoke):
        result = analyze_jd({"raw_jd": "Backend Engineer at Acme"})
        assert result["jd_data"]["title"] == "Backend Engineer"
        assert len(result["jd_data"]["requirements"]) == 2


class TestGapAnalysis:
    @patch("agent.nodes.structured_invoke", return_value=MOCK_GAP_ANALYSIS)
    def test_returns_gaps_list(self, mock_invoke):
        state = {
            "resume_data": MOCK_RESUME_DATA.model_dump(),
            "jd_data": MOCK_JD_DATA.model_dump(),
        }
        result = gap_analysis(state)
        assert len(result["gaps"]) == 1
        assert result["gaps"][0]["requirement"] == "Docker"
        assert result["candidate_score"] == 7
        assert result["recruiter_insights"]["recommendation"] == "Hire"

    @patch("agent.nodes.structured_invoke", return_value=GapAnalysis(
        gaps=[], strengths=["all"], overall_match_pct=100, candidate_score=9,
        recruiter_insights=RecruiterInsight(hiring_risks=[], recommendation="Strong Hire", justification="Excellent fit."),
    ))
    def test_no_gaps(self, mock_invoke):
        state = {
            "resume_data": MOCK_RESUME_DATA.model_dump(),
            "jd_data": MOCK_JD_DATA.model_dump(),
        }
        result = gap_analysis(state)
        assert result["gaps"] == []


class TestTailorResume:
    @patch("agent.nodes.structured_invoke", return_value=MOCK_TAILORED_BULLETS)
    def test_returns_tailored_bullets(self, mock_invoke):
        state = {
            "resume_data": MOCK_RESUME_DATA.model_dump(),
            "gaps": [{"requirement": "Docker", "importance": "nice-to-have", "assessment": "Missing"}],
        }
        result = tailor_resume(state)
        assert len(result["tailored_bullets"]) == 1
        assert result["tailored_bullets"][0]["gap_addressed"] == "Docker"


class TestGenerateCoverLetter:
    @patch("agent.nodes.invoke_with_retry")
    def test_returns_cover_letter_string(self, mock_retry):
        mock_retry.return_value = MagicMock(content="Dear Hiring Manager,\n...")
        state = {
            "resume_data": MOCK_RESUME_DATA.model_dump(),
            "jd_data": MOCK_JD_DATA.model_dump(),
            "tailored_bullets": [],
        }
        result = generate_cover_letter(state)
        assert "Dear Hiring Manager" in result["cover_letter"]


class TestGenerateInterviewQs:
    @patch("agent.nodes.structured_invoke", return_value=MOCK_INTERVIEW_QS)
    def test_returns_questions(self, mock_invoke):
        state = {
            "jd_data": MOCK_JD_DATA.model_dump(),
            "gaps": [],
            "num_questions": 5,
        }
        result = generate_interview_qs(state)
        assert len(result["interview_questions"]) == 2

    @patch("agent.nodes.structured_invoke", return_value=MOCK_INTERVIEW_QS)
    def test_uses_custom_question_count_in_prompt(self, mock_invoke):
        state = {
            "jd_data": MOCK_JD_DATA.model_dump(),
            "gaps": [],
            "num_questions": 25,
        }
        generate_interview_qs(state)
        prompt = mock_invoke.call_args[0][1]
        assert "25" in prompt

    @patch("agent.nodes.structured_invoke", return_value=MOCK_INTERVIEW_QS)
    def test_defaults_to_10_questions(self, mock_invoke):
        state = {"jd_data": MOCK_JD_DATA.model_dump(), "gaps": []}
        generate_interview_qs(state)
        prompt = mock_invoke.call_args[0][1]
        assert "10" in prompt


class TestRouteAfterGapAnalysis:
    def test_has_gaps(self):
        assert route_after_gap_analysis({"gaps": [{"requirement": "Docker"}]}) == "has_gaps"

    def test_no_gaps(self):
        assert route_after_gap_analysis({"gaps": []}) == "no_gaps"

    def test_missing_gaps_key(self):
        assert route_after_gap_analysis({}) == "no_gaps"
