import os
from pathlib import Path

from sqlalchemy import create_engine, text

TEST_DATABASE_URL = "sqlite:///./test_nipe_provider_quota_schema_compatibility.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import clear_settings_cache
from app.database import get_engine, get_session_factory, init_db, reset_engine
from app.models import ProviderQuota
from app.services.quota import consume_quota


def setup_module() -> None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    clear_settings_cache()
    reset_engine()
    db_file = Path("test_nipe_provider_quota_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE provider_quota ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "provider VARCHAR(100) NOT NULL, "
                "day_key VARCHAR(20) NOT NULL, "
                "calls_used INTEGER NOT NULL DEFAULT 0, "
                "max_calls_per_day INTEGER NOT NULL, "
                "blocked BOOLEAN NOT NULL DEFAULT 0"
                ")"
            )
        )
        connection.execute(text("CREATE UNIQUE INDEX uq_provider_day ON provider_quota (provider, day_key)"))
        connection.execute(
            text(
                "INSERT INTO provider_quota (provider, day_key, calls_used, max_calls_per_day, blocked) "
                "VALUES ('openrouter', '2026-02-28', 1, 10, 0)"
            )
        )
    engine.dispose()

    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_provider_quota_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_init_db_backfills_legacy_provider_quota_schema() -> None:
    session = get_session_factory()()
    try:
        row = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one()
        assert row.scope_key == "global"
        assert row.last_rate_limit_status is None
        assert row.last_rate_limit_status_at is None
        assert row.last_rate_limit_reset_at is None
        assert row.last_successful_call_at is None

        allowed, count = consume_quota(
            session=session,
            provider="openrouter",
            max_calls_per_day=10,
            project_id=1,
            principal_type="user",
            principal_id="alice",
        )
        assert allowed is True
        assert count == 1

        rows = (
            session.query(ProviderQuota)
            .filter(ProviderQuota.provider == "openrouter")
            .order_by(ProviderQuota.scope_key.asc())
            .all()
        )
        assert [entry.scope_key for entry in rows] == ["global", "project:1|principal:user:alice"]
    finally:
        session.close()

    engine = get_engine()
    with engine.begin() as connection:
        columns = {row["name"] for row in connection.execute(text("PRAGMA table_info(provider_quota)")).mappings()}
    assert {
        "scope_key",
        "last_rate_limit_status",
        "last_rate_limit_status_at",
        "last_rate_limit_reset_at",
        "last_successful_call_at",
    }.issubset(columns)
