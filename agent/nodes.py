"""LangGraph node functions for the Job Application Agent."""

import json

from agent.llm import llm, invoke_with_retry, structured_invoke
from agent.models import (
    ResumeData, JDData, GapAnalysis, TailoredBullets, InterviewQuestions,
)
from agent.state import AgentState


def parse_resume(state: AgentState) -> dict:
    result = structured_invoke(
        ResumeData,
        f"Extract structured information from this resume. "
        f"Be thorough — capture ALL skills, experiences, and education entries.\n\n"
        f"RESUME TEXT:\n{state['raw_resume']}",
        "parse_resume",
    )
    return {"resume_data": result.model_dump()}


def analyze_jd(state: AgentState) -> dict:
    result = structured_invoke(
        JDData,
        f"Extract structured information from this job description. "
        f"Classify each requirement as either 'must-have' or 'nice-to-have'.\n\n"
        f"JOB DESCRIPTION:\n{state['raw_jd']}",
        "analyze_jd",
    )
    return {"jd_data": result.model_dump()}


def gap_analysis(state: AgentState) -> dict:
    resume_json = json.dumps(state["resume_data"], indent=2)
    jd_json = json.dumps(state["jd_data"], indent=2)
    result = structured_invoke(
        GapAnalysis,
        f"Compare this resume against the job description requirements. "
        f"Identify which requirements are NOT met (gaps) and which ARE met (strengths). "
        f"Be realistic — partial matches count as gaps.\n\n"
        f"RESUME DATA:\n{resume_json}\n\nJOB DESCRIPTION DATA:\n{jd_json}",
        "gap_analysis",
    )
    return {"gaps": [g.model_dump() for g in result.gaps]}


def tailor_resume(state: AgentState) -> dict:
    resume_json = json.dumps(state["resume_data"], indent=2)
    gaps_json = json.dumps(state["gaps"], indent=2)
    result = structured_invoke(
        TailoredBullets,
        f"You are a professional resume writer. Rewrite or add bullet points "
        f"to better address the gaps.\n\n"
        f"Rules:\n"
        f"- Do NOT invent experience the candidate doesn't have\n"
        f"- Reframe existing experience to highlight transferable skills\n"
        f"- For genuine gaps, suggest bullets that acknowledge adjacent experience\n"
        f"- Keep bullets concise and achievement-oriented (use metrics where possible)\n\n"
        f"RESUME DATA:\n{resume_json}\n\nGAPS TO ADDRESS:\n{gaps_json}",
        "tailor_resume",
    )
    return {"tailored_bullets": [b.model_dump() for b in result.bullets]}


def generate_cover_letter(state: AgentState) -> dict:
    resume_json = json.dumps(state["resume_data"], indent=2)
    jd_json = json.dumps(state["jd_data"], indent=2)
    tailored_json = json.dumps(state.get("tailored_bullets", []), indent=2)
    response = invoke_with_retry(
        llm,
        f"Write a professional cover letter for this candidate applying to this job.\n\n"
        f"Rules:\n"
        f"- Keep it under 400 words\n"
        f"- Open with genuine enthusiasm for the role, not generic filler\n"
        f"- Highlight 2-3 strongest matches between resume and JD\n"
        f"- If tailored bullets exist, weave them in naturally\n"
        f"- Close with a confident call to action\n"
        f"- Do NOT include placeholders like [Your Name] — use the candidate's actual name\n\n"
        f"RESUME:\n{resume_json}\n\nJOB DESCRIPTION:\n{jd_json}\n\n"
        f"TAILORED BULLETS (if any):\n{tailored_json}",
        "generate_cover_letter",
    )
    return {"cover_letter": response.content}


def generate_interview_qs(state: AgentState) -> dict:
    jd_json = json.dumps(state["jd_data"], indent=2)
    gaps_json = json.dumps(state.get("gaps", []), indent=2)
    num = state.get("num_questions", 10)
    result = structured_invoke(
        InterviewQuestions,
        f"Generate {num} likely interview questions for this job.\n"
        f"Include a mix of:\n"
        f"- Technical questions based on required skills\n"
        f"- Behavioral questions (STAR format prompts)\n"
        f"- Questions that probe the identified gaps\n\n"
        f"JOB DESCRIPTION:\n{jd_json}\n\nCANDIDATE GAPS:\n{gaps_json}",
        "generate_interview_qs",
    )
    return {"interview_questions": result.questions}


def route_after_gap_analysis(state: AgentState) -> str:
    return "has_gaps" if state.get("gaps") else "no_gaps"
