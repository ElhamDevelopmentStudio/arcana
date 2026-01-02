from datetime import date, datetime, timezone
from sqlalchemy.orm import Session

from app.models import ProviderApiKeyQuota, ProviderQuota


_RATE_LIMIT_STATUS_QUOTA_REACHED = "quota_reached"
_RATE_LIMIT_STATUS_TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
_RATE_LIMIT_STATUS_AVAILABLE = "available"


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _provider_is_temporarily_blocked_until_reset(quota: ProviderQuota | ProviderApiKeyQuota, now: datetime) -> bool:
    if quota.last_rate_limit_status != _RATE_LIMIT_STATUS_TEMPORARILY_UNAVAILABLE:
        return False

    reset_at = _ensure_utc(quota.last_rate_limit_reset_at)
    if reset_at is None:
        return True

    return now < reset_at


def is_provider_available_for_request(session: Session, provider: str, max_calls_per_day: int) -> bool:
    day_key = date.today().isoformat()
    now = datetime.now(timezone.utc)

    normalized_provider = str(provider).strip().lower()
    if not normalized_provider:
        return False

    row = (
        session.query(ProviderQuota)
        .filter(ProviderQuota.provider == normalized_provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )

    if row is None:
        return True

    if row.blocked:
        if _provider_is_temporarily_blocked_until_reset(row, now):
            return row.calls_used < max_calls_per_day
        return False

    return row.calls_used < max_calls_per_day


def is_api_key_available_for_request(
    session: Session,
    provider: str,
    provider_api_key: str,
    max_calls_per_day: int,
) -> bool:
    day_key = date.today().isoformat()
    now = datetime.now(timezone.utc)

    normalized_provider = str(provider).strip().lower()
    normalized_key = str(provider_api_key).strip()
    if not normalized_provider or not normalized_key:
        return False

    row = (
        session.query(ProviderApiKeyQuota)
        .filter(
            ProviderApiKeyQuota.provider == normalized_provider,
            ProviderApiKeyQuota.provider_api_key == normalized_key,
            ProviderApiKeyQuota.day_key == day_key,
        )
        .one_or_none()
    )

    if row is None:
        return True

    if row.blocked:
        if _provider_is_temporarily_blocked_until_reset(row, now):
            return row.calls_used < max_calls_per_day
        return False

    return row.calls_used < max_calls_per_day


def _refresh_rate_limit_status(quota: ProviderQuota, status: str | None) -> None:
    quota.last_rate_limit_status = status
    if status is None:
        quota.last_rate_limit_status_at = None
    else:
        quota.last_rate_limit_status_at = datetime.now(timezone.utc)


def consume_quota(session: Session, provider: str, max_calls_per_day: int) -> tuple[bool, int]:
    day_key = date.today().isoformat()
    now = datetime.now(timezone.utc)

    quota = (
        session.query(ProviderQuota)
        .filter(ProviderQuota.provider == provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )

    if quota is None:
        quota = ProviderQuota(
            provider=provider,
            day_key=day_key,
            calls_used=0,
            max_calls_per_day=max_calls_per_day,
            blocked=False,
        )
        session.add(quota)
        session.flush()

    quota.max_calls_per_day = max_calls_per_day

    if (
        quota.blocked
        and quota.last_rate_limit_status == _RATE_LIMIT_STATUS_TEMPORARILY_UNAVAILABLE
        and _ensure_utc(quota.last_rate_limit_reset_at) is not None
        and now >= _ensure_utc(quota.last_rate_limit_reset_at)
    ):
        quota.blocked = False
        _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_AVAILABLE)

    if quota.blocked or quota.calls_used >= quota.max_calls_per_day:
        quota.blocked = True
        if not quota.last_rate_limit_status:
            _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_QUOTA_REACHED)
        session.flush()
        return False, quota.calls_used

    quota.calls_used += 1
    quota.blocked = quota.calls_used >= quota.max_calls_per_day
    if not quota.blocked:
        _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_AVAILABLE)
    session.flush()
    return True, quota.calls_used


def consume_api_key_quota(
    session: Session,
    provider: str,
    provider_api_key: str,
    max_calls_per_day: int,
) -> tuple[bool, int]:
    day_key = date.today().isoformat()
    now = datetime.now(timezone.utc)
    api_key = str(provider_api_key).strip()
    if not api_key:
        return False, 0

    quota = (
        session.query(ProviderApiKeyQuota)
        .filter(
            ProviderApiKeyQuota.provider == provider,
            ProviderApiKeyQuota.provider_api_key == api_key,
            ProviderApiKeyQuota.day_key == day_key,
        )
        .one_or_none()
    )

    if quota is None:
        quota = ProviderApiKeyQuota(
            provider=provider,
            provider_api_key=api_key,
            day_key=day_key,
            calls_used=0,
            max_calls_per_day=max_calls_per_day,
            blocked=False,
        )
        session.add(quota)
        session.flush()

    quota.max_calls_per_day = max_calls_per_day

    if (
        quota.blocked
        and quota.last_rate_limit_status == _RATE_LIMIT_STATUS_TEMPORARILY_UNAVAILABLE
        and _ensure_utc(quota.last_rate_limit_reset_at) is not None
        and now >= _ensure_utc(quota.last_rate_limit_reset_at)
    ):
        quota.blocked = False
        _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_AVAILABLE)

    if quota.blocked or quota.calls_used >= quota.max_calls_per_day:
        quota.blocked = True
        if not quota.last_rate_limit_status:
            _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_QUOTA_REACHED)
        session.flush()
        return False, quota.calls_used

    quota.calls_used += 1
    quota.blocked = quota.calls_used >= quota.max_calls_per_day
    if not quota.blocked:
        _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_AVAILABLE)
    session.flush()
    return True, quota.calls_used


def mark_api_key_rate_limited(
    session: Session,
    provider: str,
    provider_api_key: str,
    day_key: str | None = None,
) -> None:
    if day_key is None:
        day_key = date.today().isoformat()

    api_key = str(provider_api_key).strip()
    if not api_key:
        return

    quota = (
        session.query(ProviderApiKeyQuota)
        .filter(
            ProviderApiKeyQuota.provider == provider,
            ProviderApiKeyQuota.provider_api_key == api_key,
            ProviderApiKeyQuota.day_key == day_key,
        )
        .one_or_none()
    )
    if quota is None:
        return

    _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_TEMPORARILY_UNAVAILABLE)
    quota.blocked = True
    quota.last_rate_limit_reset_at = None
    session.flush()


def mark_api_key_reset_at(
    session: Session,
    provider: str,
    provider_api_key: str,
    reset_at: datetime | None,
    day_key: str | None = None,
) -> None:
    if reset_at is None:
        return
    if day_key is None:
        day_key = date.today().isoformat()

    api_key = str(provider_api_key).strip()
    if not api_key:
        return

    quota = (
        session.query(ProviderApiKeyQuota)
        .filter(
            ProviderApiKeyQuota.provider == provider,
            ProviderApiKeyQuota.provider_api_key == api_key,
            ProviderApiKeyQuota.day_key == day_key,
        )
        .one_or_none()
    )
    if quota is None:
        return

    quota.last_rate_limit_reset_at = _ensure_utc(reset_at)
    session.flush()


def mark_api_key_available(session: Session, provider: str, provider_api_key: str, day_key: str | None = None) -> None:
    if day_key is None:
        day_key = date.today().isoformat()

    api_key = str(provider_api_key).strip()
    if not api_key:
        return

    quota = (
        session.query(ProviderApiKeyQuota)
        .filter(
            ProviderApiKeyQuota.provider == provider,
            ProviderApiKeyQuota.provider_api_key == api_key,
            ProviderApiKeyQuota.day_key == day_key,
        )
        .one_or_none()
    )
    if quota is None:
        return

    _refresh_rate_limit_status(quota=quota, status=_RATE_LIMIT_STATUS_AVAILABLE)
    quota.blocked = False
    session.flush()


def mark_api_key_successful_call(
    session: Session,
    provider: str,
    provider_api_key: str,
    day_key: str | None = None,
) -> None:
    if day_key is None:
        day_key = date.today().isoformat()

    api_key = str(provider_api_key).strip()
    if not api_key:
        return

    quota = (
        session.query(ProviderApiKeyQuota)
        .filter(
            ProviderApiKeyQuota.provider == provider,
            ProviderApiKeyQuota.provider_api_key == api_key,
            ProviderApiKeyQuota.day_key == day_key,
        )
        .one_or_none()
    )
    if quota is None:
        return

    quota.last_successful_call_at = datetime.now(timezone.utc)
    session.flush()


def mark_provider_rate_limited(session: Session, provider: str, day_key: str | None = None) -> None:
    if day_key is None:
        day_key = date.today().isoformat()

    quota = (
        session.query(ProviderQuota)
        .filter(ProviderQuota.provider == provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )
    if quota is None:
        return

    _refresh_rate_limit_status(
        quota=quota,
        status=_RATE_LIMIT_STATUS_TEMPORARILY_UNAVAILABLE,
    )
    quota.blocked = True
    quota.last_rate_limit_reset_at = None
    session.flush()


def mark_provider_reset_at(
    session: Session,
    provider: str,
    reset_at: datetime | None,
    day_key: str | None = None,
) -> None:
    if reset_at is None:
        return
    if day_key is None:
        day_key = date.today().isoformat()

    quota = (
        session.query(ProviderQuota)
        .filter(ProviderQuota.provider == provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )
    if quota is None:
        return

    quota.last_rate_limit_reset_at = _ensure_utc(reset_at)
    session.flush()


def mark_provider_available(session: Session, provider: str, day_key: str | None = None) -> None:
    if day_key is None:
        day_key = date.today().isoformat()

    quota = (
        session.query(ProviderQuota)
        .filter(ProviderQuota.provider == provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )
    if quota is None:
        return

    _refresh_rate_limit_status(
        quota=quota,
        status=_RATE_LIMIT_STATUS_AVAILABLE,
    )
    quota.blocked = False
    session.flush()


def mark_provider_successful_call(session: Session, provider: str, day_key: str | None = None) -> None:
    if day_key is None:
        day_key = date.today().isoformat()

    quota = (
        session.query(ProviderQuota)
        .filter(ProviderQuota.provider == provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )
    if quota is None:
        return

    quota.last_successful_call_at = datetime.now(timezone.utc)
    session.flush()


def get_provider_request_count(session: Session, provider: str, day_key: str | None = None) -> int:
    if day_key is None:
        day_key = date.today().isoformat()

    row = (
        session.query(ProviderQuota.calls_used)
        .filter(ProviderQuota.provider == provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )

    return 0 if row is None else int(row[0])
