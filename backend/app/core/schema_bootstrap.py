"""Ensure critical DB schema exists (idempotent dev bootstrap)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS_DIR = _PROJECT_ROOT / "database" / "migrations"


def _run_sql_file(engine: Engine, filename: str) -> None:
    path = _MIGRATIONS_DIR / filename
    if not path.exists():
        logger.warning("Migration file missing: %s", path)
        return

    sql = path.read_text(encoding="utf-8")
    # Strip line comments; split on semicolons for simple migration scripts.
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buffer))
            buffer = []
    if buffer:
        statements.append("\n".join(buffer))

    with engine.begin() as conn:
        for statement in statements:
            stmt = statement.strip().rstrip(";").strip()
            if stmt:
                conn.execute(text(stmt))


def ensure_database_schema(engine: Engine) -> None:
    """Apply missing tables/columns required by current ORM models."""
    insp = inspect(engine)
    table_names = set(insp.get_table_names())

    if "users" in table_names:
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "risk_flag" not in user_cols:
            logger.info("Adding missing users.risk_flag column")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN risk_flag TINYINT UNSIGNED NOT NULL "
                        "DEFAULT 0 COMMENT '风险标记：0正常 1预警 2限速' AFTER enrollment_year"
                    )
                )

    if "verification_codes" not in table_names:
        logger.info("Applying migration 005_add_verification_codes.sql")
        _run_sql_file(engine, "005_add_verification_codes.sql")

    if "system_config" not in table_names or "ai_usage_logs" not in table_names:
        logger.info("Applying migration 006_add_system_config.sql")
        _run_sql_file(engine, "006_add_system_config.sql")
    elif "users" in table_names:
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "risk_flag" not in user_cols:
            logger.info("Applying risk_flag portion of 006_add_system_config.sql")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN risk_flag TINYINT UNSIGNED NOT NULL "
                        "DEFAULT 0 COMMENT '风险标记：0正常 1预警 2限速' AFTER enrollment_year"
                    )
                )

    if "ukl_slice" not in table_names:
        logger.info("Applying migration 007_add_ukl_slice.sql")
        _run_sql_file(engine, "007_add_ukl_slice.sql")

    if "chat_session_summary" not in table_names:
        logger.info("Applying migration 008_add_chat_session_summary.sql")
        _run_sql_file(engine, "008_add_chat_session_summary.sql")

    if "memory_embedding" not in table_names:
        logger.info("Applying migration 009_add_memory_embedding.sql")
        _run_sql_file(engine, "009_add_memory_embedding.sql")
