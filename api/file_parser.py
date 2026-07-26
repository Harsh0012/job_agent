"""Resume file text extraction."""

import io

from fastapi import HTTPException
from PyPDF2 import PdfReader


def extract_text(content: bytes, content_type: str) -> str:
    """Extract plain text from uploaded file bytes. Raises HTTPException on failure."""
    if content_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            return "".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not read PDF. The file may be corrupted or password-protected.",
            )

    if content_type in ("text/plain", "text/markdown"):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Could not decode text file. Ensure it is UTF-8 encoded.",
            )

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type: {content_type}. Use PDF or TXT.",
    )
