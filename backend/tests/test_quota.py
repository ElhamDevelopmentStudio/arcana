import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.models import ProviderQuota
from app.services.quota import (
    consume_quota,
    get_provider_request_count,
    mark_provider_available,
    mark_provider_rate_limited,
    mark_provider_reset_at,
)

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
        assert quota.last_rate_limit_status == "quota_reached"
        assert quota.last_rate_limit_status_at is not None
    finally:
        session.close()


def test_consume_quota_resumes_after_rate_limit_reset() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        provider = "openrouter"

        allow_first, count_first = consume_quota(session=session, provider=provider, max_calls_per_day=10)
        assert allow_first is True
        assert count_first == 1

        mark_provider_rate_limited(session=session, provider=provider)
        past_window = datetime.now(timezone.utc) - timedelta(minutes=1)
        mark_provider_reset_at(session=session, provider=provider, reset_at=past_window)

        allow_after_window, count_after_window = consume_quota(session=session, provider=provider, max_calls_per_day=10)
        assert allow_after_window is True
        assert count_after_window == 2

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == provider).one()
        assert quota.blocked is False
        assert quota.last_rate_limit_status == "available"
    finally:
        session.close()


def test_mark_provider_available_clears_temporary_unavailability() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        provider = "siliconflow"
        _, _ = consume_quota(session=session, provider=provider, max_calls_per_day=10)
        mark_provider_rate_limited(session=session, provider=provider)

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == provider).one()
        assert quota.blocked is True
        assert quota.last_rate_limit_status == "temporarily_unavailable"

        mark_provider_available(session=session, provider=provider)

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == provider).one()
        assert quota.blocked is False
        assert quota.last_rate_limit_status == "available"
    finally:
        session.close()
