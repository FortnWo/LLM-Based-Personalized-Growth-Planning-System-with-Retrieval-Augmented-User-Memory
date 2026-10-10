"""Optional Qdrant index for UKL memory facts."""

from __future__ import annotations

from threading import Lock
from typing import Any

from app.core.config import settings

_client: Any | None = None
_client_lock = Lock()


class VectorStoreError(RuntimeError):
    """Raised when the configured vector store cannot complete an operation."""


def is_enabled() -> bool:
    return bool(settings.VECTOR_STORE_ENABLED and settings.VECTOR_STORE_BACKEND.lower() == "qdrant")


def _get_client() -> Any:
    global _client
    if not is_enabled():
        raise VectorStoreError("Vector store is disabled")
    with _client_lock:
        if _client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise VectorStoreError("qdrant-client is not installed") from exc
            kwargs: dict[str, Any] = {
                "url": settings.VECTOR_STORE_URL,
                "timeout": settings.VECTOR_STORE_TIMEOUT_SECONDS,
            }
            if settings.VECTOR_STORE_API_KEY:
                kwargs["api_key"] = settings.VECTOR_STORE_API_KEY
            _client = QdrantClient(**kwargs)
        return _client


def ensure_collection(*, vector_size: int | None = None) -> None:
    client = _get_client()
    size = vector_size or settings.EMBEDDING_DIMENSIONS
    try:
        from qdrant_client.models import Distance, VectorParams

        existing = {item.name for item in client.get_collections().collections}
        if settings.VECTOR_STORE_COLLECTION not in existing:
            client.create_collection(
                collection_name=settings.VECTOR_STORE_COLLECTION,
                vectors_config=VectorParams(size=size, distance=Distance.COSINE),
            )
            return

        collection = client.get_collection(settings.VECTOR_STORE_COLLECTION)
        configured_size = collection.config.params.vectors.size
        if configured_size != size:
            raise VectorStoreError(
                f"Vector dimension mismatch: collection={configured_size}, requested={size}"
            )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(f"Could not initialize Qdrant collection: {exc}") from exc


def recreate_collection(*, vector_size: int | None = None) -> None:
    """Delete and recreate the configured collection for an explicit rebuild."""
    client = _get_client()
    try:
        client.delete_collection(settings.VECTOR_STORE_COLLECTION)
    except Exception as exc:
        message = str(exc).lower()
        if "not found" not in message and "doesn't exist" not in message:
            raise VectorStoreError(f"Could not rebuild Qdrant collection: {exc}") from exc
    ensure_collection(vector_size=vector_size)


def upsert_memory_fact(*, slice_id: int, embedding: list[float], payload: dict[str, Any]) -> None:
    client = _get_client()
    ensure_collection(vector_size=len(embedding))
    try:
        from qdrant_client.models import PointStruct

        client.upsert(
            collection_name=settings.VECTOR_STORE_COLLECTION,
            points=[PointStruct(id=slice_id, vector=embedding, payload=payload)],
            wait=True,
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(f"Could not upsert memory fact {slice_id}: {exc}") from exc


def search_memory_facts(
    *, user_id: int, embedding: list[float], limit: int, score_threshold: float
) -> list[dict[str, Any]]:
    client = _get_client()
    ensure_collection(vector_size=len(embedding))
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        response = client.query_points(
            collection_name=settings.VECTOR_STORE_COLLECTION,
            query=embedding,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        points = getattr(response, "points", response) or []
        return [
            {
                "slice_id": point.id,
                "fact": str((point.payload or {}).get("fact") or "").strip(),
                "score": float(point.score),
            }
            for point in points
            if str((point.payload or {}).get("fact") or "").strip()
        ]
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(f"Could not search Qdrant memory facts: {exc}") from exc


def delete_memory_fact(slice_id: int) -> None:
    client = _get_client()
    try:
        client.delete(
            collection_name=settings.VECTOR_STORE_COLLECTION,
            points_selector=[slice_id],
            wait=True,
        )
    except Exception as exc:
        raise VectorStoreError(f"Could not delete memory fact {slice_id}: {exc}") from exc


def healthcheck() -> bool:
    try:
        _get_client().get_collections()
        return True
    except Exception:
        return False


def reset_client() -> None:
    """Reset the lazy client for tests and process reconfiguration."""
    global _client
    with _client_lock:
        _client = None