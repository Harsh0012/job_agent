"""Pipeline runner — wraps the graph with vector store caching."""

import json
import logging
from collections.abc import Generator

from agent.graph import graph
from agent.vector_store import find_similar_analysis, store_analysis, CACHEABLE_KEYS

logger = logging.getLogger(__name__)

_ALL_NODES = (
    "parse_resume", "analyze_jd", "gap_analysis",
    "tailor_resume", "generate_cover_letter", "generate_interview_qs",
)


def _check_cache(raw_jd: str, num_questions: int) -> dict | None:
    """Return cached result if valid, else None."""
    try:
        cached = find_similar_analysis(raw_jd)
        if cached:
            cached_qs = len(cached.get("interview_questions") or [])
            if cached_qs == num_questions:
                cached["cached"] = True
                return cached
            logger.info(f"Cache hit but question count differs ({cached_qs} vs {num_questions}), re-running.")
    except Exception as e:
        logger.warning(f"Vector store lookup failed, running fresh: {e}")
    return None


def _cache_result(raw_jd: str, state: dict) -> None:
    """Attempt to cache the pipeline result."""
    try:
        store_analysis(raw_jd, state)
    except Exception as e:
        logger.warning(f"Failed to cache result in vector store: {e}")


def run_pipeline(raw_resume: str, raw_jd: str, num_questions: int = 10) -> dict:
    """Run the full analysis pipeline with caching."""
    cached = _check_cache(raw_jd, num_questions)
    if cached:
        return cached

    result = graph.invoke({"raw_resume": raw_resume, "raw_jd": raw_jd, "num_questions": num_questions})
    _cache_result(raw_jd, result)
    result["cached"] = False
    return result


def run_pipeline_stream(raw_resume: str, raw_jd: str, num_questions: int = 10) -> Generator[str, None, None]:
    """Run the pipeline with SSE streaming — yields 'event: ...' strings."""
    cached = _check_cache(raw_jd, num_questions)
    if cached:
        for node in _ALL_NODES:
            yield f"event: step\ndata: {json.dumps({'node': node, 'status': 'done'})}\n\n"
        yield f"event: result\ndata: {json.dumps(cached)}\n\n"
        return

    final_state = {}
    for chunk in graph.stream({"raw_resume": raw_resume, "raw_jd": raw_jd, "num_questions": num_questions}):
        for node_name, node_output in chunk.items():
            final_state.update(node_output)
            yield f"event: step\ndata: {json.dumps({'node': node_name, 'status': 'done'})}\n\n"

    _cache_result(raw_jd, final_state)
    result = {k: final_state.get(k) for k in CACHEABLE_KEYS}
    result["cached"] = False
    yield f"event: result\ndata: {json.dumps(result)}\n\n"
