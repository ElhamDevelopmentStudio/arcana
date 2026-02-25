import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mode_profile_loader.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.modes import MODE_DEFAULT_PROFILES, MODE_VALUES
from app.services.mode_profiles import load_mode_profile, load_mode_profile_catalog, normalize_mode_value

EXPECTED_CUSTOM_PROFILE = {
    "max_segment_chars": 255,
    "llm_enabled": False,
    "provider_name": "openrouter",
    "max_calls_per_day": 25,
    "profile_intent": "user-tuned baseline with conservative defaults",
}


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mode_profile_loader.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_loader_normalizes_mode_and_returns_profile_copy() -> None:
    assert normalize_mode_value("  ACADEMIC ") == "academic"
    assert normalize_mode_value(None) == "audiobook"
    assert normalize_mode_value(" ") == "audiobook"

    profile = load_mode_profile("academic")
    assert profile == MODE_DEFAULT_PROFILES["academic"]

    profile["max_segment_chars"] = 111
    assert MODE_DEFAULT_PROFILES["academic"]["max_segment_chars"] == 220


def test_integration_loader_catalog_includes_all_modes() -> None:
    profile_catalog = load_mode_profile_catalog()
    assert set(profile_catalog.keys()) == set(MODE_VALUES)
    assert profile_catalog == MODE_DEFAULT_PROFILES


def test_e2e_modes_endpoint_returns_loader_catalog_profiles() -> None:
    with TestClient(app) as client:
        response = client.get("/api/modes")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode_profiles"] == load_mode_profile_catalog()


def test_regression_custom_profile_loader_snapshot() -> None:
    assert load_mode_profile("custom") == EXPECTED_CUSTOM_PROFILE
