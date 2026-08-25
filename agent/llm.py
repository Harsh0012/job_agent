"""LLM configuration and retry logic."""

import logging
import time
from typing import Type

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")

MAX_RETRIES = 3
RETRY_DELAY = 5

_RETRYABLE_KEYWORDS = ("rate_limit", "429", "timeout", "connection", "503", "overloaded", "resource_exhausted")


def _normalize_content(response):
    """Gemini returns content as a list of parts; extract the text."""
    if isinstance(response.content, list):
        response.content = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in response.content
        )
    return response


def invoke_with_retry(llm_instance, prompt: str, node_name: str):
    """Call the LLM with retry logic for rate limits and transient errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _normalize_content(llm_instance.invoke(prompt))
        except Exception as e:
            error_msg = str(e).lower()
            retryable = any(kw in error_msg for kw in _RETRYABLE_KEYWORDS)
            if retryable and attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                logger.warning(f"[{node_name}] Attempt {attempt} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"[{node_name}] Failed after {attempt} attempt(s): {e}")
                raise


def structured_invoke(model_class: Type[BaseModel], prompt: str, node_name: str):
    """Invoke the LLM with structured output and retry logic."""
    return invoke_with_retry(llm.with_structured_output(model_class), prompt, node_name)
