"""Pipeline runner — wraps the graph with vector store caching."""

import json
import logging
from collections.abc import Generator

from agent.graph import graph
from agent.vector_store import find_similar_analysis, store_analysis

logger = logging.getLogger(__name__)

_CACHEABLE_KEYS = (
    "resume_data", "jd_data", "gaps",
    "tailored_bullets", "cover_letter", "interview_questions",
)


def run_pipeline(raw_resume: str, raw_jd: str, num_questions: int = 10) -> dict:
    """Run the full analysis pipeline with caching.

    Returns:
        dict with keys: resume_data, jd_data, gaps, tailored_bullets,
        cover_letter, interview_questions, and a 'cached' boolean flag.
    """
    # Try cache lookup — if it fails, just skip caching gracefully.
    try:
        cached_result = find_similar_analysis(raw_jd)
        if cached_result:
            cached_qs = len(cached_result.get("interview_questions") or [])
            if cached_qs == num_questions:
                cached_result["cached"] = True
                return cached_result
            logger.info(f"Cache hit but question count differs ({cached_qs} vs {num_questions}), re-running.")
    except Exception as e:
        logger.warning(f"Vector store lookup failed, running fresh: {e}")

    result = graph.invoke({
        "raw_resume": raw_resume,
        "raw_jd": raw_jd,
        "num_questions": num_questions,
    })

    # Try to cache — if it fails, still return the result.
    try:
        store_analysis(raw_jd, result)
    except Exception as e:
        logger.warning(f"Failed to cache result in vector store: {e}")

    result["cached"] = False
    return result


def run_pipeline_stream(raw_resume: str, raw_jd: str, num_questions: int = 10) -> Generator[str, None, None]:
    """Run the pipeline with SSE streaming — yields 'event: ...' strings."""

    # Check cache first
    try:
        cached_result = find_similar_analysis(raw_jd)
        if cached_result:
            cached_qs = len(cached_result.get("interview_questions") or [])
            if cached_qs == num_questions:
                # Emit all steps as done instantly, then the cached result
                for node in ("parse_resume", "analyze_jd", "gap_analysis",
                             "tailor_resume", "generate_cover_letter", "generate_interview_qs"):
                    yield f"event: step\ndata: {json.dumps({'node': node, 'status': 'done'})}\n\n"
                cached_result["cached"] = True
                yield f"event: result\ndata: {json.dumps(cached_result)}\n\n"
                return
            logger.info(f"Cache hit but question count differs ({cached_qs} vs {num_questions}), re-running.")
    except Exception as e:
        logger.warning(f"Vector store lookup failed, running fresh: {e}")

    # Stream the graph execution
    initial_state = {"raw_resume": raw_resume, "raw_jd": raw_jd, "num_questions": num_questions}
    final_state = {}

    for chunk in graph.stream(initial_state):
        for node_name, node_output in chunk.items():
            final_state.update(node_output)
            yield f"event: step\ndata: {json.dumps({'node': node_name, 'status': 'done'})}\n\n"

    # Cache the result
    try:
        store_analysis(raw_jd, final_state)
    except Exception as e:
        logger.warning(f"Failed to cache result in vector store: {e}")

    # Build and emit final result
    result = {k: final_state.get(k) for k in _CACHEABLE_KEYS}
    result["cached"] = False
    yield f"event: result\ndata: {json.dumps(result)}\n\n"
