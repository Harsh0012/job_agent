"""FastAPI backend for the Job Application Agent."""

import asyncio
import logging
import os
import queue
import threading

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent.pipeline import run_pipeline, run_pipeline_stream
from api.file_parser import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
RESULT_KEYS = (
    "cached", "resume_data", "jd_data", "gaps",
    "tailored_bullets", "cover_letter", "interview_questions",
)

app = FastAPI(title="Job Application Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ["http://localhost:4200", os.getenv("FRONTEND_URL", "")] if o],
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _validate_inputs(content: bytes, resume_content_type: str, job_description: str) -> tuple[str, str]:
    """Validate and parse upload inputs. Returns (resume_text, job_description)."""
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Resume file exceeds 5 MB limit.")

    resume_text = extract_text(content, resume_content_type)

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume file is empty or contains no extractable text.")
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is empty.")

    return resume_text, job_description.strip()


@app.get("/api/health")
def health():
    key = os.getenv("GOOGLE_API_KEY", "")
    return {"status": "ok", "llm_configured": bool(key)}


@app.post("/api/analyze")
async def analyze(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    num_questions: int = Form(default=10),
):
    content = await resume.read()
    resume_text, jd = _validate_inputs(content, resume.content_type, job_description)
    num_questions = max(5, min(num_questions, 30))

    try:
        result = await asyncio.to_thread(
            run_pipeline, raw_resume=resume_text, raw_jd=jd, num_questions=num_questions,
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
    resume_text, jd = _validate_inputs(content, resume.content_type, job_description)
    num_questions = max(5, min(num_questions, 30))

    async def event_generator():
        q: queue.Queue[str | None] = queue.Queue()

        def _run():
            try:
                for event in run_pipeline_stream(raw_resume=resume_text, raw_jd=jd, num_questions=num_questions):
                    q.put(event)
            except Exception as e:
                logger.error(f"Stream pipeline failed: {e}", exc_info=True)
                q.put(f"event: error\ndata: {{\"detail\": \"Analysis failed. Please try again.\"}}\n\n")
            finally:
                q.put(None)

        threading.Thread(target=_run, daemon=True).start()

        while True:
            event = await asyncio.get_event_loop().run_in_executor(None, q.get)
            if event is None:
                break
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
