import os
from pathlib import Path

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.models import ProviderQuota
from app.services.quota import consume_quota, get_provider_request_count

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_quota.db"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_quota.db")
    if db_file.exists():
        db_file.unlink()


def test_consume_quota_tracks_counts_by_provider() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        allowed_openrouter_1, request_count_openrouter_1 = consume_quota(
            session=session, provider="openrouter", max_calls_per_day=2
        )
        allowed_openrouter_2, request_count_openrouter_2 = consume_quota(
            session=session, provider="openrouter", max_calls_per_day=2
        )
        allowed_siliconflow_1, request_count_siliconflow_1 = consume_quota(
            session=session, provider="siliconflow", max_calls_per_day=2
        )

        openrouter_usage = get_provider_request_count(session, "openrouter")
        siliconflow_usage = get_provider_request_count(session, "siliconflow")
        provider_counts = {row.provider: row.calls_used for row in session.query(ProviderQuota).all()}

        assert allowed_openrouter_1 is True
        assert request_count_openrouter_1 == 1
        assert allowed_openrouter_2 is True
        assert request_count_openrouter_2 == 2
        assert allowed_siliconflow_1 is True
        assert request_count_siliconflow_1 == 1

        assert provider_counts["openrouter"] == 2
        assert provider_counts["siliconflow"] == 1
        assert openrouter_usage == 2
        assert siliconflow_usage == 1
    finally:
        session.close()


def test_consume_quota_blocks_after_provider_limit() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        allowed_once, count_once = consume_quota(session=session, provider="openrouter", max_calls_per_day=1)
        allowed_second, count_second = consume_quota(session=session, provider="openrouter", max_calls_per_day=1)
        allowed_third, count_third = consume_quota(session=session, provider="openrouter", max_calls_per_day=1)

        assert allowed_once is True
        assert count_once == 1
        assert allowed_second is False
        assert count_second == 1
        assert allowed_third is False
        assert count_third == 1

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one()
        assert quota.blocked is True
    finally:
        session.close()
