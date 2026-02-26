import os
import io
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_chapter_content_integrity.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app, _build_run_artifact_integrity_report
from app.models import ProjectRawCorpusBlob, Run, RunChangelogEntry, RunNormalizedCorpusBlob
from app.services import pipeline


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_chapter_content_integrity.db")
    if db_file.exists():
        db_file.unlink()


def _ingest_project(project_title: str, source_text: str) -> int:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(source_text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        return project_id


def test_chapter_content_integrity_report_passes_and_fails_for_mismatch() -> None:
    report = pipeline._build_chapter_content_integrity_report(
        chapters=[
            SimpleNamespace(chapter_index=1, normalized_text="Chapter one text for integrity check."),
        ],
        segment_payloads=[
            {
                "chapter_id": 1,
                "segment_id": "1-001",
                "segment_index": 1,
                "normalized_text": "Chapter",
                "original_text": "Chapter",
                "original_span_pointer": {
                    "original_start_char": 0,
                    "original_end_char": 0,
                    "normalized_start_char": 0,
                    "normalized_end_char": 7,
                },
            },
            {
                "chapter_id": 1,
                "segment_id": "1-002",
                "segment_index": 2,
                "normalized_text": " one text for integrity check.",
                "original_text": " one text for integrity check.",
                "original_span_pointer": {
                    "original_start_char": 0,
                    "original_end_char": 0,
                    "normalized_start_char": 7,
                    "normalized_end_char": 37,
                },
            },
        ],
    )
    assert report["is_content_preserved"] is True
    assert report["mismatched_chapters"] == []

    failing_report = pipeline._build_chapter_content_integrity_report(
        chapters=[
            SimpleNamespace(chapter_index=1, normalized_text="Chapter one text for integrity check."),
        ],
        segment_payloads=[
            {
                "chapter_id": 1,
                "segment_id": "1-001",
                "segment_index": 1,
                "normalized_text": "Chapter",
                "original_text": "Chapter",
                "original_span_pointer": {
                    "original_start_char": 0,
                    "original_end_char": 0,
                    "normalized_start_char": -1,
                    "normalized_end_char": -1,
                },
            },
        ],
    )
    assert failing_report["is_content_preserved"] is False
    assert failing_report["mismatched_chapters"]


def test_pipeline_run_records_chapter_content_integrity() -> None:
    project_id = _ingest_project(
        project_title="Integrity Check Project",
        source_text=(
            "Chapter 1\n"
            "A calm wind rolled over the valley as the sun dropped.\n\n"
            "Chapter 2\n"
            "Lightning broke the dark horizon and silence answered."
        ),
    )

    with TestClient(app) as client:
        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80, "llm_enabled": False})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()
        integrity = detail_payload["config"]["chapter_content_integrity"]
        assert integrity["is_content_preserved"] is True
        assert integrity["mismatched_chapters"] == []


def test_pipeline_run_records_artifact_integrity() -> None:
    project_id = _ingest_project(
        project_title="Artifact Integrity Project",
        source_text=(
            "Chapter 1\n"
            "The lantern burned low across the hall.\n\n"
            "Chapter 2\n"
            "Rain began, and silence followed."
        ),
    )

    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "llm_enabled": False, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        artifact_integrity = detail_resp.json()["config"].get("artifact_integrity")

        assert artifact_integrity["is_artifact_integrity_intact"] is True
        checks = artifact_integrity["checks"]
        assert {entry["artifact"] for entry in checks} >= {
            "run_normalized_corpus_blob",
            "run_configuration_snapshot",
            "character_map_snapshot",
            "pronunciation_dictionary_snapshot",
            "voice_map_snapshot",
            "time_series_snapshot",
        }
        assert all(entry["passed"] for entry in checks)


@pytest.mark.parametrize(
    "artifact_name, get_snapshot",
    [
        ("run_configuration_snapshot", lambda run: run.run_configuration_snapshot),
        ("character_map_snapshot", lambda run: run.character_map_snapshot),
        ("pronunciation_dictionary_snapshot", lambda run: run.pronunciation_dictionary_snapshot),
        ("voice_map_snapshot", lambda run: run.voice_map_snapshot),
        ("time_series_snapshot", lambda run: run.time_series_snapshot),
    ],
)
def test_pipeline_run_records_corrupt_snapshot_payload_fails_integrity(
    artifact_name: str,
    get_snapshot,
) -> None:
    project_id = _ingest_project(
        project_title=f"Snapshot Corruption {artifact_name.title()} Project",
        source_text=(
            "Chapter 1\n"
            "The lantern burned low across the hall.\n"
            "Rain began, and silence followed."
        ),
    )

    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "llm_enabled": False, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        baseline_report = _build_run_artifact_integrity_report(session=session, run=run)
        assert baseline_report["is_artifact_integrity_intact"] is True

        snapshot = get_snapshot(run)
        assert snapshot is not None
        assert isinstance(snapshot.snapshot_json, dict)

        snapshot.snapshot_json = dict(snapshot.snapshot_json) | {"__integrity_probe": "tampered"}
        session.add(snapshot)
        session.commit()

        report = _build_run_artifact_integrity_report(session=session, run=run)
        assert report["is_artifact_integrity_intact"] is False
        checks = {entry["artifact"]: entry for entry in report["checks"]}
        assert checks[artifact_name]["passed"] is False
        assert checks[artifact_name]["details"]["payload_hash_mismatch"] is True
        assert "payload_hash_mismatch" in checks[artifact_name]["details"]
    finally:
        session.close()


def test_run_artifact_integrity_report_detects_corrupt_normalized_blob() -> None:
    project_id = _ingest_project(
        project_title="Artifact Integrity Corruption Project",
        source_text=(
            "Chapter 1\n"
            "Nora opened the gate and called to Taro.\n"
            "The city waited."
        ),
    )

    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "llm_enabled": False, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()

        baseline_report = _build_run_artifact_integrity_report(session=session, run=run)
        assert baseline_report["is_artifact_integrity_intact"] is True

        corrupted_blob = (
            session.query(RunNormalizedCorpusBlob)
            .filter(RunNormalizedCorpusBlob.run_id == run.id)
            .one()
        )
        corrupted_blob.corpus_sha256 = "corrupted"
        session.add(corrupted_blob)
        session.commit()

        report = _build_run_artifact_integrity_report(session=session, run=run)
        assert report["is_artifact_integrity_intact"] is False

        checks = {entry["artifact"]: entry for entry in report["checks"]}
        assert checks["run_normalized_corpus_blob"]["passed"] is False
        assert checks["run_normalized_corpus_blob"]["details"]["reason"] == "hash_mismatch"
    finally:
        session.close()


def test_run_detail_revalidates_artifact_integrity_on_corpus_corruption() -> None:
    project_id = _ingest_project(
        project_title="Artifact Integrity Live Recheck Project",
        source_text=(
            "Chapter 1\n"
            "A bell tolled once while the sky dimmed.\n"
            "A promise broke quietly."
        ),
    )

    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "llm_enabled": False, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        raw_corpus_blob = (
            session.query(ProjectRawCorpusBlob)
            .filter(ProjectRawCorpusBlob.project_id == project_id)
            .order_by(ProjectRawCorpusBlob.id.asc())
            .first()
        )
        assert raw_corpus_blob is not None
        raw_corpus_blob.raw_corpus_blob = b"tampered"
        session.add(raw_corpus_blob)
        session.commit()

        with TestClient(app) as client:
            detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
            assert detail_resp.status_code == 200
            artifact_integrity = detail_resp.json()["config"]["artifact_integrity"]

        assert artifact_integrity["is_artifact_integrity_intact"] is False
        checks = {entry["artifact"]: entry for entry in artifact_integrity["checks"]}
        assert checks["project_raw_corpus_blobs"]["passed"] is False
        assert checks["project_raw_corpus_blobs"]["details"]["mismatch_count"] == 1

        run = session.query(Run).filter(Run.id == run_id).one()
        run_config = run.config_json
        assert run_config["artifact_integrity"]["is_artifact_integrity_intact"] is False
    finally:
        session.close()


def test_pipeline_run_fails_when_content_integrity_is_broken() -> None:
    project_id = _ingest_project(
        project_title="Integrity Broken Project",
        source_text="Chapter 1\nThe gate should hold the town together.",
    )

    def _broken_chunk_payload(*_, **__):
        return {
            "chunk_index": 1,
            "chunk_count": 1,
            "segment_payloads": [
                {
                    "chapter_id": 1,
                    "chapter_internal_id": "ch-0001",
                    "segment_id": "1-001",
                    "segment_index": 1,
                    "original_text": "broken",
                    "normalized_text": "broken",
                    "original_span_pointer": {
                        "original_start_char": 0,
                        "original_end_char": 0,
                        "normalized_start_char": -1,
                        "normalized_end_char": -1,
                    },
                },
            ],
            "sub_segment_payloads": [[]],
            "llm_probe_text": "broken",
        }

    with patch("app.services.pipeline._build_chunk_segment_payloads", _broken_chunk_payload):
        with TestClient(app) as client:
            run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80, "llm_enabled": False})
            assert run_resp.status_code == 400
            assert "chapter-content integrity check failed" in run_resp.text

    session = get_session_factory()()
    try:
        latest_run = session.query(Run).filter(Run.project_id == project_id).order_by(Run.id.desc()).first()
        assert latest_run is not None
        assert latest_run.status == "failed"

        failure_entry = (
            session.query(RunChangelogEntry)
            .filter(
                RunChangelogEntry.run_id == latest_run.id,
                RunChangelogEntry.event_type == "pipeline_failed",
            )
            .order_by(RunChangelogEntry.id.desc())
            .first()
        )
        assert failure_entry is not None
        metadata = failure_entry.event_metadata or {}
        assert metadata["reason"] == "chapter-content integrity check failed during chapter reconstruction"
        assert metadata["metadata"]["chapter_content_integrity"]["is_content_preserved"] is False
    finally:
        session.close()
