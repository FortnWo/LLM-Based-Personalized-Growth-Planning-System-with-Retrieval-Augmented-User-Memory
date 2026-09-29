"""UKL5 事实记忆：对话轮次抽取、向量写入与 Tier2 检索。

写路径：LLM 抽取 fact/salience 后写入 ukl_slice 与 memory_embedding；
读路径：按 query 门控 + cosine/关键词检索，供 chat_context 注入 [相关事实记忆]。
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import SLICE_TYPE_MEMORY_FACT, SOURCE_MODULE_MEMORY_FACT
from app.models.memory_embedding import MemoryEmbedding
from app.models.ukl_slice import UklSlice
from app.schemas.ukl import MemoryFactPayload
logger = logging.getLogger(__name__)

_TIER2_KEYWORDS = (
    "之前",
    "记得",
    "进度",
    "上次",
    "以前",
    "延续",
    "什么时候",
    "哪次",
    "具体",
    "核实",
    "还记得",
    "说过",
    "约定",
    "计划过",
)

_SMALL_TALK_KEYWORDS = ("你好", "您好", "谢谢", "在吗", "早上好", "晚上好", "嗨", "hello", "hi")
_MIN_SUBSTANTIVE_CHARS = 8


def should_trigger_tier2_retrieval(query: str) -> bool:
    """根据关键词与消息长度判断是否启用 Tier2 事实检索（避免寒暄误触发）。"""
    text = (query or "").strip()
    if not text:
        return False
    return any(keyword in text for keyword in _TIER2_KEYWORDS)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _deserialize_payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def should_extract_facts(user_message: str, assistant_message: str) -> bool:
    if not settings.UKL_ENABLED or not settings.MEMORY_FACT_ENABLED:
        return False
    if not settings.MEMORY_FACT_EXTRACTION_ENABLED:
        return False

    user_text = (user_message or "").strip()
    assistant_text = (assistant_message or "").strip()
    if len(user_text) < _MIN_SUBSTANTIVE_CHARS and len(assistant_text) < _MIN_SUBSTANTIVE_CHARS:
        return False

    combined = f"{user_text} {assistant_text}".lower()
    if len(user_text) < _MIN_SUBSTANTIVE_CHARS and any(keyword in combined for keyword in _SMALL_TALK_KEYWORDS):
        return False
    if user_text in _SMALL_TALK_KEYWORDS and len(assistant_text) < _MIN_SUBSTANTIVE_CHARS:
        return False

    return True


def has_facts_for_message(db: Session, user_id: int, message_id: int) -> bool:
    rows = (
        db.query(UklSlice)
        .filter(
            UklSlice.user_id == user_id,
            UklSlice.slice_type == SLICE_TYPE_MEMORY_FACT,
        )
        .all()
    )
    for row in rows:
        payload = _deserialize_payload(row.payload)
        if payload.get("message_id") == message_id:
            return True
    return False


def _store_embedding(db: Session, *, user_id: int, slice_id: int, embedding: list[float]) -> None:
    model_name = settings.EMBEDDING_MODEL
    existing = db.query(MemoryEmbedding).filter(MemoryEmbedding.slice_id == slice_id).first()
    serialized = json.dumps(embedding)
    if existing:
        existing.model = model_name
        existing.dimensions = len(embedding)
        existing.embedding_json = serialized
        db.add(existing)
        return

    db.add(
        MemoryEmbedding(
            user_id=user_id,
            slice_id=slice_id,
            model=model_name,
            dimensions=len(embedding),
            embedding_json=serialized,
        )
    )


def _index_memory_fact(
    *,
    user_id: int,
    slice_id: int,
    embedding: list[float],
    fact: str,
    salience: float,
    session_id: int | None,
    message_id: int | None,
) -> None:
    if not settings.VECTOR_STORE_ENABLED:
        return
    try:
        from app.services import vector_store

        vector_store.upsert_memory_fact(
            slice_id=slice_id,
            embedding=embedding,
            payload={
                "user_id": user_id,
                "slice_id": slice_id,
                "model": settings.EMBEDDING_MODEL,
                "dimensions": len(embedding),
                "fact": fact,
                "salience": salience,
                "session_id": session_id,
                "message_id": message_id,
            },
        )
    except Exception:
        logger.exception("Memory fact vector index failed user_id=%s slice_id=%s", user_id, slice_id)
        if settings.VECTOR_STORE_STRICT:
            raise


def ingest_memory_fact(
    db: Session,
    user_id: int,
    *,
    fact: str,
    session_id: int | None,
    message_id: int | None,
    salience: float,
    tags: list[str] | None = None,
) -> UklSlice | None:
    text = (fact or "").strip()
    if not text:
        return None
    if salience < settings.MEMORY_FACT_MIN_SALIENCE:
        return None

    payload = MemoryFactPayload(
        fact=text,
        session_id=session_id,
        message_id=message_id,
        salience=salience,
        occurred_at=datetime.utcnow(),
        tags=tags or [],
    )
    slice_row = UklSlice(
        user_id=user_id,
        slice_type=SLICE_TYPE_MEMORY_FACT,
        source_module=SOURCE_MODULE_MEMORY_FACT,
        ref_type=None,
        ref_id=None,
        payload=json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
        version=1,
    )
    db.add(slice_row)
    db.flush()

    if settings.MEMORY_FACT_EMBEDDING_ENABLED:
        try:
            from app.services import ai_service

            embedding = ai_service.create_embedding(text)
            if embedding:
                _store_embedding(db, user_id=user_id, slice_id=slice_row.id, embedding=embedding)
                _index_memory_fact(
                    user_id=user_id,
                    slice_id=slice_row.id,
                    embedding=embedding,
                    fact=text,
                    salience=salience,
                    session_id=session_id,
                    message_id=message_id,
                )
        except Exception:
            logger.exception("Memory fact embedding failed slice_id=%s", slice_row.id)

    return slice_row


def _keyword_search_facts(
    db: Session,
    user_id: int,
    query: str,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    query_text = (query or "").strip().lower()
    if not query_text:
        return []

    rows = (
        db.query(UklSlice)
        .filter(
            UklSlice.user_id == user_id,
            UklSlice.slice_type == SLICE_TYPE_MEMORY_FACT,
        )
        .order_by(UklSlice.updated_at.desc(), UklSlice.id.desc())
        .all()
    )
    hits: list[dict[str, Any]] = []
    for row in rows:
        payload = _deserialize_payload(row.payload)
        fact = str(payload.get("fact") or "").strip()
        if not fact:
            continue
        if any(token in fact.lower() for token in query_text.split() if len(token) >= 2):
            hits.append({"slice_id": row.id, "fact": fact, "score": 0.75})
        if len(hits) >= top_k:
            break
    return hits


def search_memory_facts(
    db: Session,
    user_id: int,
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[dict[str, Any]]:
    if not settings.UKL_ENABLED or not settings.MEMORY_FACT_ENABLED:
        return []

    limit = top_k if top_k is not None else settings.MEMORY_FACT_TOP_K
    threshold = min_score if min_score is not None else settings.MEMORY_FACT_MIN_SCORE
    query_text = (query or "").strip()
    if not query_text:
        return []

    if settings.MEMORY_FACT_EMBEDDING_ENABLED:
        try:
            from app.services import ai_service

            query_embedding = ai_service.create_embedding(query_text)
        except Exception:
            logger.exception("Memory fact query embedding failed user_id=%s", user_id)
            query_embedding = None

        if query_embedding:
            if settings.VECTOR_STORE_ENABLED:
                try:
                    from app.services import vector_store

                    vector_hits = vector_store.search_memory_facts(
                        user_id=user_id,
                        embedding=query_embedding,
                        limit=limit,
                        score_threshold=threshold,
                    )
                    if vector_hits:
                        return vector_hits
                except Exception:
                    logger.exception("Memory fact vector search failed user_id=%s", user_id)
                    if settings.VECTOR_STORE_STRICT:
                        raise

            rows = (
                db.query(MemoryEmbedding, UklSlice)
                .join(UklSlice, UklSlice.id == MemoryEmbedding.slice_id)
                .filter(MemoryEmbedding.user_id == user_id, UklSlice.slice_type == SLICE_TYPE_MEMORY_FACT)
                .all()
            )
            scored: list[dict[str, Any]] = []
            for embedding_row, slice_row in rows:
                try:
                    vector = json.loads(embedding_row.embedding_json)
                except json.JSONDecodeError:
                    continue
                if not isinstance(vector, list):
                    continue
                score = cosine_similarity(query_embedding, [float(v) for v in vector])
                if score < threshold:
                    continue
                payload = _deserialize_payload(slice_row.payload)
                fact = str(payload.get("fact") or "").strip()
                if not fact:
                    continue
                scored.append({"slice_id": slice_row.id, "fact": fact, "score": score})

            scored.sort(key=lambda item: item["score"], reverse=True)
            return scored[:limit]

    return _keyword_search_facts(db, user_id, query_text, top_k=limit)


def parse_extraction_result(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []

    results: list[dict[str, Any]] = []
    for item in loaded:
        if not isinstance(item, dict):
            continue
        fact = str(item.get("fact") or "").strip()
        if not fact:
            continue
        try:
            salience = float(item.get("salience", 0.5))
        except (TypeError, ValueError):
            salience = 0.5
        tags_raw = item.get("tags") or []
        tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()] if isinstance(tags_raw, list) else []
        results.append({"fact": fact, "salience": salience, "tags": tags})
    return results


def extract_and_ingest_facts_for_turn(
    db: Session,
    *,
    user_id: int,
    session_id: int,
    message_id: int,
    user_message: str,
    assistant_message: str,
    session_summary: str | None = None,
) -> int:
    """从单轮对话抽取事实并写入 UKL；返回本次新增事实条数。"""
    if not should_extract_facts(user_message, assistant_message):
        return 0
    if has_facts_for_message(db, user_id, message_id):
        return 0

    from app.services import ai_service

    dialogue = f"用户: {user_message.strip()}\n助手: {assistant_message.strip()}"
    if session_summary and session_summary.strip():
        dialogue = f"会话摘要:\n{session_summary.strip()}\n\n{dialogue}"

    try:
        raw = ai_service.build_memory_fact_extraction_response(dialogue)
    except Exception:
        logger.exception("Memory fact extraction LLM failed user_id=%s message_id=%s", user_id, message_id)
        return 0

    candidates = parse_extraction_result(raw)[: settings.MEMORY_FACT_MAX_PER_TURN]
    ingested = 0
    for candidate in candidates:
        row = ingest_memory_fact(
            db,
            user_id,
            fact=candidate["fact"],
            session_id=session_id,
            message_id=message_id,
            salience=candidate["salience"],
            tags=candidate.get("tags"),
        )
        if row is not None:
            ingested += 1
    return ingested
