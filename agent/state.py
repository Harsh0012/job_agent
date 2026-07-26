"""Shared state definition for the Job Application Agent."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    raw_resume: str
    raw_jd: str
    num_questions: int
    resume_data: dict
    jd_data: dict
    gaps: list
    tailored_bullets: list
    cover_letter: str
    interview_questions: list
