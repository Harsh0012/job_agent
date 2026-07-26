"""LLM configuration and retry logic."""

import logging
import time
from typing import Type

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

MAX_RETRIES = 3
RETRY_DELAY = 5

_RETRYABLE_KEYWORDS = ("rate_limit", "429", "timeout", "connection", "503", "overloaded")


def invoke_with_retry(llm_instance, prompt: str, node_name: str):
    """Call the LLM with retry logic for rate limits and transient errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return llm_instance.invoke(prompt)
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
