"""API endpoint tests — requires the FastAPI server running on port 8000."""

import httpx
import pytest

from tests.conftest import SAMPLE_RESUME, SAMPLE_JD

BASE = "http://127.0.0.1:8000"


def _post_analyze(files=None, data=None, timeout=30):
    return httpx.post(f"{BASE}/api/analyze", files=files, data=data, timeout=timeout)


def _resume_file(content: bytes = b"", name: str = "resume.txt", mime: str = "text/plain"):
    return {"resume": (name, content or SAMPLE_RESUME.encode(), mime)}


class TestHealth:
    def test_returns_ok(self):
        r = httpx.get(f"{BASE}/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestAnalyzeSuccess:
    def test_full_analysis(self):
        r = _post_analyze(
            files=_resume_file(),
            data={"job_description": SAMPLE_JD},
            timeout=120,
        )
        assert r.status_code == 200
        body = r.json()
        for key in ("resume_data", "jd_data", "gaps", "cover_letter", "interview_questions"):
            assert body.get(key) is not None, f"Missing key: {key}"
        assert "cached" in body

    def test_cache_hit_on_repeat(self):
        r = _post_analyze(
            files=_resume_file(),
            data={"job_description": SAMPLE_JD},
            timeout=120,
        )
        assert r.status_code == 200
        assert r.json()["cached"] is True


class TestAnalyzeValidation:
    def test_empty_resume_returns_400(self):
        r = _post_analyze(
            files=_resume_file(b"   "),
            data={"job_description": SAMPLE_JD},
        )
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_empty_jd_returns_400(self):
        r = _post_analyze(
            files=_resume_file(),
            data={"job_description": "   "},
        )
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_unsupported_file_type_returns_400(self):
        r = _post_analyze(
            files=_resume_file(b"fake", "doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            data={"job_description": SAMPLE_JD},
        )
        assert r.status_code == 400

    def test_missing_resume_returns_422(self):
        r = _post_analyze(data={"job_description": SAMPLE_JD})
        assert r.status_code == 422

    def test_corrupted_pdf_returns_400(self):
        r = _post_analyze(
            files=_resume_file(b"not a real pdf", "resume.pdf", "application/pdf"),
            data={"job_description": SAMPLE_JD},
        )
        assert r.status_code == 400
        assert "could not read" in r.json()["detail"].lower()

    def test_oversized_file_returns_400(self):
        big = b"A" * (5 * 1024 * 1024 + 1)
        r = _post_analyze(
            files=_resume_file(big, "big.txt"),
            data={"job_description": SAMPLE_JD},
        )
        assert r.status_code == 400
        assert "5 mb" in r.json()["detail"].lower()
