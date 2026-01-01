from datetime import date
from sqlalchemy.orm import Session

from app.models import ProviderQuota


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
        session.flush()
        return False, quota.calls_used

    quota.calls_used += 1
    quota.blocked = quota.calls_used >= quota.max_calls_per_day
    session.flush()
    return True, quota.calls_used


def get_provider_request_count(session: Session, provider: str, day_key: str | None = None) -> int:
    if day_key is None:
        day_key = date.today().isoformat()

    row = (
        session.query(ProviderQuota.calls_used)
        .filter(ProviderQuota.provider == provider, ProviderQuota.day_key == day_key)
        .one_or_none()
    )

    return 0 if row is None else int(row[0])
