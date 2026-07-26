"""Pydantic models for structured LLM output."""

from pydantic import BaseModel, Field


class Experience(BaseModel):
    company: str = Field(description="Company or organization name")
    role: str = Field(description="Job title / role")
    duration: str = Field(description="Time period, e.g. 'Jan 2020 - Mar 2022'")
    bullets: list[str] = Field(description="Key accomplishments or responsibilities")


class Education(BaseModel):
    institution: str = Field(description="University or school name")
    degree: str = Field(description="Degree obtained, e.g. 'B.Tech in CS'")
    year: str = Field(description="Graduation year or period")


class ResumeData(BaseModel):
    name: str = Field(description="Candidate's full name")
    skills: list[str] = Field(description="Technical and soft skills listed")
    experience: list[Experience] = Field(description="Work experience entries")
    education: list[Education] = Field(description="Education entries")
    summary: str = Field(description="Brief professional summary if present, else empty string")


class JDRequirement(BaseModel):
    skill: str = Field(description="Required skill or qualification")
    importance: str = Field(description="'must-have' or 'nice-to-have'")


class JDData(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name if mentioned, else 'Unknown'")
    requirements: list[JDRequirement] = Field(description="All listed requirements")
    responsibilities: list[str] = Field(description="Key job responsibilities")
    experience_years: str = Field(description="Required years of experience, e.g. '3-5 years'")


class Gap(BaseModel):
    requirement: str = Field(description="The JD requirement that is not fully met")
    importance: str = Field(description="'must-have' or 'nice-to-have'")
    assessment: str = Field(description="Brief explanation of why this is a gap")


class GapAnalysis(BaseModel):
    gaps: list[Gap] = Field(description="Requirements the resume does NOT fully satisfy")
    strengths: list[str] = Field(description="Requirements the resume clearly meets")
    overall_match_pct: int = Field(description="Estimated match percentage 0-100")


class TailoredBullet(BaseModel):
    original: str = Field(description="The original resume bullet point (or 'NEW' if freshly added)")
    tailored: str = Field(description="The rewritten bullet point addressing a gap")
    gap_addressed: str = Field(description="Which gap this bullet helps address")


class TailoredBullets(BaseModel):
    bullets: list[TailoredBullet] = Field(description="List of tailored bullet points")


class InterviewQuestions(BaseModel):
    questions: list[str] = Field(description="Likely interview questions based on the job description")
