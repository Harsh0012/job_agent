"""FastAPI backend for the Job Application Agent."""

import asyncio
import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent.pipeline import run_pipeline, run_pipeline_stream
from api.file_parser import extract_text

import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
RESULT_KEYS = (
    "cached", "resume_data", "jd_data", "gaps",
    "tailored_bullets", "cover_letter", "interview_questions",
)

CORS_ORIGINS = [
    "http://localhost:4200",
    os.getenv("FRONTEND_URL", "https://job-agent-frontend.onrender.com"),
]

app = FastAPI(title="Job Application Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    num_questions: int = Form(default=10),
):
    content = await resume.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Resume file exceeds 5 MB limit.")

    resume_text = extract_text(content, resume.content_type)

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume file is empty or contains no extractable text.")
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is empty.")

    num_questions = max(5, min(num_questions, 30))  # clamp between 5-30

    try:
        result = await asyncio.to_thread(
            run_pipeline,
            raw_resume=resume_text,
            raw_jd=job_description,
            num_questions=num_questions,
        )
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. The AI service may be temporarily unavailable. Please try again in a minute.",
        )

    return {k: result.get(k) for k in RESULT_KEYS}


@app.post("/api/analyze/stream")
async def analyze_stream(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    num_questions: int = Form(default=10),
):
    content = await resume.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Resume file exceeds 5 MB limit.")

    resume_text = extract_text(content, resume.content_type)

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume file is empty or contains no extractable text.")
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is empty.")

    num_questions = max(5, min(num_questions, 30))

    async def event_generator():
        try:
            gen = run_pipeline_stream(
                raw_resume=resume_text,
                raw_jd=job_description,
                num_questions=num_questions,
            )
            for event in gen:
                yield event
        except Exception as e:
            logger.error(f"Stream pipeline failed: {e}", exc_info=True)
            yield f"event: error\ndata: {{\"detail\": \"Analysis failed. Please try again.\"}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
