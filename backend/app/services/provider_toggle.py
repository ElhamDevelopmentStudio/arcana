from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ProviderToggle
from app.services.llm_router import get_provider_priority_order, is_supported_provider


def _normalize_provider_name(value: object) -> str:
    return str(value).strip().lower()


def is_provider_enabled(session: Session, provider: str) -> bool:
    provider_name = _normalize_provider_name(provider)
    if not provider_name or not is_supported_provider(provider_name):
        return False

    for pending_toggle in session.new:
        if isinstance(pending_toggle, ProviderToggle) and _normalize_provider_name(pending_toggle.provider) == provider_name:
            return bool(pending_toggle.enabled)

    for dirty_toggle in session.dirty:
        if isinstance(dirty_toggle, ProviderToggle) and _normalize_provider_name(dirty_toggle.provider) == provider_name:
            return bool(dirty_toggle.enabled)

    row = session.query(ProviderToggle).filter(ProviderToggle.provider == provider_name).one_or_none()
    if row is None:
        return True
    return bool(row.enabled)


def set_provider_enabled(session: Session, provider: str, enabled: bool) -> bool:
    provider_name = _normalize_provider_name(provider)
    if not is_supported_provider(provider_name):
        raise ValueError("Unsupported provider")

    row = session.query(ProviderToggle).filter(ProviderToggle.provider == provider_name).one_or_none()
    if row is None:
        row = ProviderToggle(provider=provider_name, enabled=bool(enabled))
        session.add(row)
    else:
        row.enabled = bool(enabled)

    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return bool(row.enabled)


def get_provider_statuses(session: Session, settings: object | None = None) -> list[tuple[str, bool]]:
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    ordered_providers = get_provider_priority_order(settings=settings)
    rows = (
        session.query(ProviderToggle.provider, ProviderToggle.enabled)
        .filter(ProviderToggle.provider.in_(ordered_providers))
        .all()
    )
    toggles: dict[str, bool] = {provider: bool(enabled) for provider, enabled in rows}

    return [(provider, toggles.get(provider, True)) for provider in ordered_providers]
