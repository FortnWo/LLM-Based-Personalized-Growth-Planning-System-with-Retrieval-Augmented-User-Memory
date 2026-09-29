import json

import pytest

from app.core.config import settings
from app.core.ukl_constants import SLICE_TYPE_MEMORY_FACT
from app.models.memory_embedding import MemoryEmbedding
from app.models.ukl_slice import UklSlice
from app.models.user import User
from app.services import ukl_memory_fact_service


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="ukl5_memory",
        email="ukl5memory@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_should_trigger_tier2_retrieval():
    assert ukl_memory_fact_service.should_trigger_tier2_retrieval("你还记得上次说的进度吗")
    assert ukl_memory_fact_service.should_trigger_tier2_retrieval("我们什么时候约定过这件事")
    assert not ukl_memory_fact_service.should_trigger_tier2_retrieval("今天天气不错")
    assert not ukl_memory_fact_service.should_trigger_tier2_retrieval("")


def test_cosine_similarity_ranks_expected_vectors():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]
    assert ukl_memory_fact_service.cosine_similarity(a, b) == pytest.approx(1.0)
    assert ukl_memory_fact_service.cosine_similarity(a, c) == pytest.approx(0.0)


def test_ingest_memory_fact_creates_slice_and_embedding(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EMBEDDING_ENABLED", True)

    monkeypatch.setattr(
        "app.services.ai_service.create_embedding",
        lambda text: [1.0, 0.2, 0.0] if "周三" in text else [0.0, 1.0, 0.0],
    )

    row = ukl_memory_fact_service.ingest_memory_fact(
        db_session,
        sample_user.id,
        fact="用户每周三晚上有空学英语",
        session_id=1,
        message_id=10,
        salience=0.9,
        tags=["schedule"],
    )
    db_session.commit()

    assert row is not None
    slice_row = (
        db_session.query(UklSlice)
        .filter(UklSlice.user_id == sample_user.id, UklSlice.slice_type == SLICE_TYPE_MEMORY_FACT)
        .one()
    )
    payload = json.loads(slice_row.payload)
    assert payload["fact"] == "用户每周三晚上有空学英语"
    assert payload["message_id"] == 10

    embedding_row = (
        db_session.query(MemoryEmbedding)
        .filter(MemoryEmbedding.slice_id == slice_row.id)
        .one()
    )
    assert json.loads(embedding_row.embedding_json) == [1.0, 0.2, 0.0]


def test_search_memory_facts_ranks_by_similarity(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_MIN_SCORE", 0.5)
    monkeypatch.setattr("app.services.ai_service.create_embedding", lambda text: [0.0, 0.0, 0.0])

    english_slice = ukl_memory_fact_service.ingest_memory_fact(
        db_session,
        sample_user.id,
        fact="用户每周三晚上有空学英语",
        session_id=1,
        message_id=11,
        salience=0.9,
    )
    running_slice = ukl_memory_fact_service.ingest_memory_fact(
        db_session,
        sample_user.id,
        fact="用户喜欢跑步",
        session_id=1,
        message_id=12,
        salience=0.8,
    )
    assert english_slice is not None and running_slice is not None
    assert english_slice.id != running_slice.id

    for row in db_session.query(MemoryEmbedding).filter(
        MemoryEmbedding.slice_id.in_([english_slice.id, running_slice.id])
    ):
        if row.slice_id == english_slice.id:
            row.embedding_json = json.dumps([1.0, 0.0, 0.0])
        else:
            row.embedding_json = json.dumps([0.0, 1.0, 0.0])
    db_session.commit()

    monkeypatch.setattr(
        "app.services.ai_service.create_embedding",
        lambda text: [0.95, 0.05, 0.0],
    )

    hits = ukl_memory_fact_service.search_memory_facts(
        db_session,
        sample_user.id,
        "之前说过什么时候学英语",
    )
    assert hits
    assert hits[0]["fact"] == "用户每周三晚上有空学英语"
    assert hits[0]["score"] >= 0.5


def test_message_id_idempotent(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EXTRACTION_ENABLED", True)

    monkeypatch.setattr(
        "app.services.ai_service.build_memory_fact_extraction_response",
        lambda msg: json.dumps(
            [{"fact": "用户每周三晚上有空学英语", "salience": 0.9, "tags": ["schedule"]}],
            ensure_ascii=False,
        ),
    )
    monkeypatch.setattr("app.services.ai_service.create_embedding", lambda text: [1.0, 0.0])

    first = ukl_memory_fact_service.extract_and_ingest_facts_for_turn(
        db_session,
        user_id=sample_user.id,
        session_id=1,
        message_id=99,
        user_message="我每周三晚上有空学英语",
        assistant_message="好的，我会记住你的时间安排。",
    )
    db_session.commit()

    second = ukl_memory_fact_service.extract_and_ingest_facts_for_turn(
        db_session,
        user_id=sample_user.id,
        session_id=1,
        message_id=99,
        user_message="我每周三晚上有空学英语",
        assistant_message="好的，我会记住你的时间安排。",
    )

    assert first == 1
    assert second == 0
    count = (
        db_session.query(UklSlice)
        .filter(UklSlice.user_id == sample_user.id, UklSlice.slice_type == SLICE_TYPE_MEMORY_FACT)
        .count()
    )
    assert count == 1


def test_salience_skips_small_talk(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EXTRACTION_ENABLED", True)

    called = {"value": False}

    def _fake_extract(message: str) -> str:
        called["value"] = True
        return "[]"

    monkeypatch.setattr("app.services.ai_service.build_memory_fact_extraction_response", _fake_extract)

    count = ukl_memory_fact_service.extract_and_ingest_facts_for_turn(
        db_session,
        user_id=sample_user.id,
        session_id=1,
        message_id=100,
        user_message="你好",
        assistant_message="你好呀",
    )
    assert count == 0
    assert called["value"] is False


def test_ingest_memory_fact_indexes_qdrant_when_enabled(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "VECTOR_STORE_ENABLED", True)
    monkeypatch.setattr("app.services.ai_service.create_embedding", lambda text: [1.0, 0.0])

    indexed = {}
    monkeypatch.setattr(
        "app.services.vector_store.upsert_memory_fact",
        lambda **kwargs: indexed.update(kwargs),
    )

    row = ukl_memory_fact_service.ingest_memory_fact(
        db_session,
        sample_user.id,
        fact="用户计划周三学习英语",
        session_id=1,
        message_id=20,
        salience=0.9,
    )

    assert row is not None
    assert indexed["slice_id"] == row.id
    assert indexed["payload"]["user_id"] == sample_user.id
    assert indexed["payload"]["fact"] == "用户计划周三学习英语"


def test_qdrant_failure_falls_back_to_json_search(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "VECTOR_STORE_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_MIN_SCORE", 0.5)
    monkeypatch.setattr("app.services.ai_service.create_embedding", lambda text: [1.0, 0.0])

    row = ukl_memory_fact_service.ingest_memory_fact(
        db_session,
        sample_user.id,
        fact="用户计划周三学习英语",
        session_id=1,
        message_id=21,
        salience=0.9,
    )
    db_session.commit()
    embedding = db_session.query(MemoryEmbedding).filter(MemoryEmbedding.slice_id == row.id).one()
    embedding.embedding_json = json.dumps([1.0, 0.0])
    db_session.commit()

    def fail_search(**kwargs):
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr("app.services.vector_store.search_memory_facts", fail_search)
    hits = ukl_memory_fact_service.search_memory_facts(
        db_session,
        sample_user.id,
        "之前说过周三学习英语",
    )

    assert hits
    assert hits[0]["fact"] == "用户计划周三学习英语"
