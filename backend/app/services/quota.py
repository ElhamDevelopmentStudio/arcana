from datetime import date, datetime, timezone
from sqlalchemy.orm import Session

from app.models import ProviderQuota


_RATE_LIMIT_STATUS_QUOTA_REACHED = "quota_reached"
_RATE_LIMIT_STATUS_PROVIDER_RATE_LIMITED = "provider_rate_limited"
_RATE_LIMIT_STATUS_AVAILABLE = "available"


def _refresh_rate_limit_status(quota: ProviderQuota, status: str | None) -> None:
    quota.last_rate_limit_status = status
    if status is None:
        quota.last_rate_limit_status_at = None
    else:
        quota.last_rate_limit_status_at = datetime.now(timezone.utc)


def consume_quota(session: Session, provider: str, max_calls_per_day: int) -> tuple[bool, int]:
    day_key = date.today().isoformat()

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
        status=_RATE_LIMIT_STATUS_PROVIDER_RATE_LIMITED,
    )
    quota.blocked = True
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

    quota.last_rate_limit_reset_at = reset_at
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
