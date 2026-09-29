from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.schema_bootstrap import ensure_database_schema


def test_ensure_database_schema_adds_risk_flag_when_missing():
    engine = MagicMock()
    insp = MagicMock()
    insp.get_table_names.return_value = ["users", "system_config", "ai_usage_logs", "verification_codes"]
    insp.get_columns.return_value = [{"name": "id"}, {"name": "username"}]

    with patch("app.core.schema_bootstrap.inspect", return_value=insp):
        ensure_database_schema(engine)

    assert engine.begin.called


def test_ensure_database_schema_applies_memory_embedding_migration():
    engine = MagicMock()
    insp = MagicMock()
    insp.get_table_names.return_value = [
        "users",
        "system_config",
        "ai_usage_logs",
        "verification_codes",
        "ukl_slice",
        "chat_session_summary",
    ]
    insp.get_columns.return_value = [{"name": "id"}, {"name": "risk_flag"}]

    with (
        patch("app.core.schema_bootstrap.inspect", return_value=insp),
        patch("app.core.schema_bootstrap._run_sql_file") as run_sql,
    ):
        ensure_database_schema(engine)

    run_sql.assert_called_once_with(engine, "009_add_memory_embedding.sql")
