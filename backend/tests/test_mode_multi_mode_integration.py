import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mode_multi_mode.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.modes import MODE_DEFAULT_PROFILES

EXPECTED_MULTI_MODE_SEQUENCE = ["audiobook", "academic", "author", "custom"]


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mode_multi_mode.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _create_ingested_project(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] == 2
    return project_id


def _run_mode(client: TestClient, project_id: int, mode: str) -> tuple[int, int]:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={"mode": mode},
    )
    assert run_resp.status_code == 200
    payload = run_resp.json()
    return int(payload["run_id"]), int(payload["segment_count"])


def test_unit_mode_sequence_for_multi_mode_integration() -> None:
    assert EXPECTED_MULTI_MODE_SEQUENCE == ["audiobook", "academic", "author", "custom"]


def test_integration_ingest_once_then_run_all_modes() -> None:
    with TestClient(app) as client:
        project_id = _create_ingested_project(client, "Multi Mode Integration")

        run_records: list[tuple[str, int, int]] = []
        for mode in EXPECTED_MULTI_MODE_SEQUENCE:
            run_id, segment_count = _run_mode(client, project_id, mode)
            run_records.append((mode, run_id, segment_count))

        for mode, run_id, segment_count in run_records:
            assert segment_count > 0
            detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
            assert detail_resp.status_code == 200
            detail_payload = detail_resp.json()
            assert detail_payload["config"]["mode"] == mode
            assert detail_payload["config"]["export_formats"] == MODE_DEFAULT_PROFILES[mode]["export_formats"]
            assert detail_payload["config"]["mode_profile_snapshot"] == MODE_DEFAULT_PROFILES[mode]

    session = get_session_factory()()
    try:
        chapter_rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert len(chapter_rows) == 2
    finally:
        session.close()


def test_e2e_all_modes_produce_exports_from_single_ingestion() -> None:
    with TestClient(app) as client:
        project_id = _create_ingested_project(client, "Multi Mode E2E")

        for mode in EXPECTED_MULTI_MODE_SEQUENCE:
            run_id, segment_count = _run_mode(client, project_id, mode)
            assert segment_count > 0

            export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
            assert export_resp.status_code == 200
            export_payload = export_resp.json()
            assert export_payload["project_id"] == project_id
            assert export_payload["run_id"] == run_id
            assert len(export_payload["segments"]) > 0
            assert export_payload["manifest"]["run"]["config_snapshot"]["mode"] == mode

            academic_export_resp = client.get(
                f"/api/projects/{project_id}/exports/{run_id}.json",
                params={"output_schema": "academic", "output_format": "json"},
            )
            assert academic_export_resp.status_code == 200

            if mode == "author":
                author_export_resp = client.get(
                    f"/api/projects/{project_id}/exports/{run_id}.json",
                    params={"output_schema": "author"},
                )
                assert author_export_resp.status_code == 200
                assert author_export_resp.json()["output_schema"] == "author_narrative_health_json"


def test_regression_multi_mode_sequence_snapshot() -> None:
    assert EXPECTED_MULTI_MODE_SEQUENCE == ["audiobook", "academic", "author", "custom"]
