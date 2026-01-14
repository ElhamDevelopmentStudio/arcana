import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.models import ProviderApiKeyQuota, ProviderQuota
from app.services.quota import (
    consume_quota,
    consume_api_key_quota,
    get_provider_request_count,
    is_api_key_available_for_request,
    is_provider_available_for_request,
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


def test_is_provider_available_for_request_is_false_after_limit_reached() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        allowed_once, _ = consume_quota(session=session, provider="openrouter", max_calls_per_day=1)
        allowed_twice, _ = consume_quota(session=session, provider="openrouter", max_calls_per_day=1)

        assert allowed_once is True
        assert allowed_twice is False
        assert is_provider_available_for_request(session=session, provider="openrouter", max_calls_per_day=1) is False
    finally:
        session.close()


def test_is_api_key_available_for_request_is_false_when_key_is_exhausted() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        provider = "groq"
        key = "quota-key"

        first, _ = consume_api_key_quota(session=session, provider=provider, provider_api_key=key, max_calls_per_day=1)
        second, _ = consume_api_key_quota(session=session, provider=provider, provider_api_key=key, max_calls_per_day=1)

        assert first is True
        assert second is False
        assert is_api_key_available_for_request(
            session=session,
            provider=provider,
            provider_api_key=key,
            max_calls_per_day=1,
        ) is False
    finally:
        session.close()


def test_scope_isolated_provider_quota_by_project_and_principal() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        provider = "openrouter"

        global_allowed, global_count = consume_quota(
            session=session,
            provider=provider,
            max_calls_per_day=1,
        )
        user_a_allowed, user_a_count = consume_quota(
            session=session,
            provider=provider,
            max_calls_per_day=1,
            project_id=1,
            principal_type="user",
            principal_id="alice",
        )
        user_b_allowed, user_b_count = consume_quota(
            session=session,
            provider=provider,
            max_calls_per_day=1,
            project_id=1,
            principal_type="user",
            principal_id="bob",
        )
        project_two_allowed, project_two_count = consume_quota(
            session=session,
            provider=provider,
            max_calls_per_day=1,
            project_id=2,
            principal_type="user",
            principal_id="alice",
        )
        global_second, global_second_count = consume_quota(
            session=session,
            provider=provider,
            max_calls_per_day=1,
            project_id=1,
            principal_type="user",
            principal_id="alice",
        )

        assert global_allowed is True
        assert global_count == 1
        assert get_provider_request_count(session, provider=provider) == 1
        assert user_a_allowed is True
        assert user_a_count == 1
        assert get_provider_request_count(session, provider=provider, project_id=1, principal_type="user", principal_id="alice") == 1
        assert user_b_allowed is True
        assert user_b_count == 1
        assert get_provider_request_count(session, provider=provider, project_id=1, principal_type="user", principal_id="bob") == 1
        assert project_two_allowed is True
        assert project_two_count == 1
        assert get_provider_request_count(session, provider=provider, project_id=2, principal_type="user", principal_id="alice") == 1
        assert global_second is False
        assert global_second_count == 1
        assert get_provider_request_count(session, provider=provider, project_id=1, principal_type="user", principal_id="alice") == 1

        quota_rows = session.query(ProviderQuota).all()
        assert len(quota_rows) == 4
        scope_keys = {row.scope_key for row in quota_rows}
        assert scope_keys == {
            "global",
            "project:1|principal:user:alice",
            "project:1|principal:user:bob",
            "project:2|principal:user:alice",
        }
    finally:
        session.close()


def test_scope_isolated_api_key_quota_by_project_and_principal() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        provider = "groq"
        api_key = "shared-key"

        consume_api_key_quota(
            session=session,
            provider=provider,
            provider_api_key=api_key,
            max_calls_per_day=1,
            project_id=1,
            principal_type="user",
            principal_id="alice",
        )
        consume_api_key_quota(
            session=session,
            provider=provider,
            provider_api_key=api_key,
            max_calls_per_day=1,
            project_id=1,
            principal_type="user",
            principal_id="bob",
        )
        consume_api_key_quota(
            session=session,
            provider=provider,
            provider_api_key=api_key,
            max_calls_per_day=1,
            project_id=2,
            principal_type="user",
            principal_id="alice",
        )

        assert (
            session.query(ProviderApiKeyQuota)
            .filter(
                ProviderApiKeyQuota.provider == provider,
                ProviderApiKeyQuota.provider_api_key == api_key,
                ProviderApiKeyQuota.scope_key == "project:1|principal:user:alice",
            )
            .one()
            .calls_used
            == 1
        )
        assert (
            session.query(ProviderApiKeyQuota)
            .filter(
                ProviderApiKeyQuota.provider == provider,
                ProviderApiKeyQuota.provider_api_key == api_key,
                ProviderApiKeyQuota.scope_key == "project:1|principal:user:bob",
            )
            .one()
            .calls_used
            == 1
        )
        assert (
            session.query(ProviderApiKeyQuota)
            .filter(
                ProviderApiKeyQuota.provider == provider,
                ProviderApiKeyQuota.provider_api_key == api_key,
                ProviderApiKeyQuota.scope_key == "project:2|principal:user:alice",
            )
            .one()
            .calls_used
            == 1
        )
    finally:
        session.close()
