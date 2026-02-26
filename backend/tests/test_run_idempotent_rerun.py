import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_idempotent_rerun.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Run


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_run_idempotent_rerun.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient) -> int:
    project_resp = client.post("/api/projects", json={"title": "Idempotent Rerun Project"})
    assert project_resp.status_code == 201
    return int(project_resp.json()["id"])


def _ingest_text(client: TestClient, project_id: int, payload: bytes) -> None:
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(payload), "text/plain")},
    )
    assert ingest_resp.status_code == 200


def _append_chapter(client: TestClient, project_id: int, payload: bytes) -> None:
    append_resp = client.post(
        f"/api/projects/{project_id}/ingest/append-chapter",
        files={"file": ("chapter-2.txt", io.BytesIO(payload), "text/plain")},
    )
    assert append_resp.status_code == 200


def _run_with_idempotency(
    client: TestClient, project_id: int, key: str, max_segment_chars: int = 120
) -> int:
    run_payload = {
        "allow_unfinalized_character_map": True,
        "idempotency_key": key,
        "max_segment_chars": max_segment_chars,
        "llm_enabled": False,
    }
    run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    assert run_resp.status_code == 200
    return int(run_resp.json()["run_id"])


def _mock_noop_pipeline(*, session, project, run, run_config):  # noqa: ARG001
    return {"segment_count": 0, "export": {"time_series": {"emotion_valence": []}}}


def test_same_idempotency_key_reuses_matching_completed_run(monkeypatch: object) -> None:
    project_text = (
        b"Chapter 1\nA lantern burned in the quiet archive, and no one noticed the door close."
    )

    def _mocked_pipeline(*, session, project, run, run_config):  # noqa: ARG001
        _mock_noop_pipeline(session=session, project=project, run=run, run_config=run_config)
        return {"segment_count": 0, "export": {"time_series": {"emotion_valence": []}}}

    call_counter = {"count": 0}

    def _counted_pipeline(*, session, project, run, run_config):  # noqa: ARG001
        call_counter["count"] += 1
        return _mocked_pipeline(session=session, project=project, run=run, run_config=run_config)

    monkeypatch.setattr("app.main.execute_pipeline", _counted_pipeline)

    with TestClient(app) as client:
        project_id = _create_project(client)
        _ingest_text(client=client, project_id=project_id, payload=project_text)

        first_run_id = _run_with_idempotency(client=client, project_id=project_id, key="rerun-key-1")
        second_run_id = _run_with_idempotency(client=client, project_id=project_id, key="rerun-key-1")

    assert call_counter["count"] == 1
    assert first_run_id == second_run_id

    session = get_session_factory()()
    try:
        assert session.query(Run).filter(Run.project_id == project_id).count() == 1
    finally:
        session.close()


def test_idempotent_signature_changes_when_payload_changes(monkeypatch: object) -> None:
    def _counted_pipeline(*, session, project, run, run_config):  # noqa: ARG001
        _counted_pipeline.call_count += 1
        return {"segment_count": 0, "export": {"time_series": {"emotion_valence": []}}}

    _counted_pipeline.call_count = 0  # type: ignore[attr-defined]
    monkeypatch.setattr("app.main.execute_pipeline", _counted_pipeline)

    with TestClient(app) as client:
        project_id = _create_project(client)
        _ingest_text(
            client=client,
            project_id=project_id,
            payload=b"Chapter 1\nThe signal tower lit up, and silence arrived with it.",
        )

        first_run_id = _run_with_idempotency(
            client=client,
            project_id=project_id,
            key="rerun-key-2",
            max_segment_chars=120,
        )
        second_run_id = _run_with_idempotency(
            client=client,
            project_id=project_id,
            key="rerun-key-2",
            max_segment_chars=200,
        )

    assert _counted_pipeline.call_count == 2
    assert first_run_id != second_run_id


def test_idempotent_signature_changes_when_corpus_changes(monkeypatch: object) -> None:
    def _counted_pipeline(*, session, project, run, run_config):  # noqa: ARG001
        _counted_pipeline.call_count += 1
        return {"segment_count": 0, "export": {"time_series": {"emotion_valence": []}}}

    _counted_pipeline.call_count = 0  # type: ignore[attr-defined]
    monkeypatch.setattr("app.main.execute_pipeline", _counted_pipeline)

    with TestClient(app) as client:
        project_id = _create_project(client)
        _ingest_text(
            client=client,
            project_id=project_id,
            payload=b"Chapter 1\nA detective watched dawn leak across the alley.",
        )

        first_run_id = _run_with_idempotency(client=client, project_id=project_id, key="rerun-key-3")

        _append_chapter(
            client=client,
            project_id=project_id,
            payload=b"Chapter 2\nA train whistle split the morning sky into shards.",
        )

        second_run_id = _run_with_idempotency(client=client, project_id=project_id, key="rerun-key-3")

    assert _counted_pipeline.call_count == 2
    assert first_run_id != second_run_id
