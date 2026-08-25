"""LLM configuration and retry logic."""

import logging
import os
import re
import time
from typing import Type

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
# max_retries=0 disables the SDK's internal retry loop on 429s
llm = ChatGoogleGenerativeAI(model=MODEL_NAME, max_retries=0)
logger.info(f"Using model: {MODEL_NAME}")

MAX_RETRIES = 2
_RATE_LIMIT_KEYWORDS = ("resource_exhausted", "rate_limit", "429")
_TRANSIENT_KEYWORDS = ("timeout", "connection", "503", "overloaded")


def _parse_retry_delay(error_msg: str) -> float:
    """Extract the server-suggested retry delay from the error message."""
    match = re.search(r"retry in ([\d.]+)s", error_msg, re.IGNORECASE)
    if match:
        return min(float(match.group(1)) + 1.0, 65.0)
    return 62.0


def _normalize_content(response):
    """Gemini returns content as a list of parts; extract the text."""
    content = getattr(response, "content", None)
    if isinstance(content, list):
        response.content = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return response


def invoke_with_retry(llm_instance, prompt: str, node_name: str):
    """Call the LLM with retry logic for rate limits and transient errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _normalize_content(llm_instance.invoke(prompt))
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = any(kw in error_msg for kw in _RATE_LIMIT_KEYWORDS)
            is_transient = any(kw in error_msg for kw in _TRANSIENT_KEYWORDS)

            if is_rate_limit and attempt < MAX_RETRIES:
                wait = _parse_retry_delay(error_msg)
                logger.warning(f"[{node_name}] Rate limited (attempt {attempt}). Waiting {wait:.0f}s...")
                time.sleep(wait)
            elif is_transient and attempt < MAX_RETRIES:
                wait = 5 * attempt
                logger.warning(f"[{node_name}] Transient error (attempt {attempt}). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"[{node_name}] Failed after {attempt} attempt(s): {e}")
                raise


def structured_invoke(model_class: Type[BaseModel], prompt: str, node_name: str):
    """Invoke the LLM with structured output and retry logic."""
    return invoke_with_retry(llm.with_structured_output(model_class), prompt, node_name)
