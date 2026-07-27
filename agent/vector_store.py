"""Chroma vector store for caching past JD analyses."""

import json
import logging
import uuid

import chromadb

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85
CACHEABLE_KEYS = (
    "resume_data", "jd_data", "gaps",
    "tailored_bullets", "cover_letter", "interview_questions",
)

_COLLECTION_NAME = "jd_analyses"

try:
    _client = chromadb.PersistentClient(path="chroma_db")
    _collection = _client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
except Exception as e:
    logger.error(f"Failed to initialize Chroma: {e}")
    _client = None
    _collection = None


def find_similar_analysis(jd_text: str) -> dict | None:
    if _collection is None or _collection.count() == 0:
        return None

    results = _collection.query(query_texts=[jd_text], n_results=1)
    if not results["distances"] or not results["distances"][0]:
        return None

    distance = results["distances"][0][0]
    similarity = 1 - distance  # cosine distance → cosine similarity

    if similarity >= SIMILARITY_THRESHOLD:
        return json.loads(results["metadatas"][0][0]["result_json"])
    return None


def store_analysis(jd_text: str, result: dict) -> None:
    if _collection is None:
        logger.warning("Chroma not available, skipping cache store.")
        return

    cacheable = {k: result.get(k) for k in CACHEABLE_KEYS}
    _collection.add(
        documents=[jd_text],
        metadatas=[{"result_json": json.dumps(cacheable)}],
        ids=[str(uuid.uuid4())],
    )
