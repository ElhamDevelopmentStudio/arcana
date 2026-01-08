import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_recovery.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app, _build_snapshot_json_checksum
from app.models import (
    Chapter,
    LLMCall,
    ProjectRawCorpusBlob,
    CharacterMapSnapshot,
    PronunciationDictionarySnapshot,
    RunConfigurationSnapshot,
    Run,
    VoiceMapSnapshot,
    RunNormalizedCorpusBlob,
    RunChangelogEntry,
    Segment,
    SubSegmentTag,
)


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_run_recovery.db")
    if db_file.exists():
        db_file.unlink()


def _create_project() -> int:
    with TestClient(app) as client:
        response = client.post("/api/projects", json={"title": "Run Recovery Project"})
        assert response.status_code == 201
        return int(response.json()["id"])


def _create_stale_run_with_artifacts(
    *,
    project_id: int,
    status: str,
    stale_minutes: float,
    pipeline_recovery: dict[str, object] | None = None,
) -> int:
    now = datetime.now(timezone.utc)
    run_config: dict[str, object] = {"mode": "academic"}
    if pipeline_recovery is not None:
        run_config["pipeline_recovery"] = dict(pipeline_recovery)

    session = get_session_factory()()
    try:
        run = Run(
            project_id=project_id,
            status=status,
            config_json=run_config,
            started_at=now - timedelta(minutes=stale_minutes),
        )
        session.add(run)
        session.flush()

        chapter = Chapter(
            project_id=project_id,
            chapter_index=1,
            chapter_internal_id="ch-1",
            chapter_title="Chapter 1",
            raw_text="Nova spoke.",
            original_text_snapshot="Nova spoke.",
            normalized_text="Nova spoke.",
            normalized_text_snapshot="Nova spoke.",
            original_to_normalized_offset_map=[],
        )
        session.add(chapter)
        session.flush()

        segment = Segment(
            run_id=run.id,
            chapter_id=chapter.id,
            segment_index=0,
            segment_json={"text": "Nova spoke."},
        )
        session.add(segment)
        session.flush()

        call = LLMCall(
            run_id=run.id,
            provider="mock-provider",
            task_type="mock-task",
            success=True,
            request_count=1,
            is_cache_hit=False,
            token_usage_estimate=None,
            called_at=now,
            detail="mock call",
            model_identifier="mock-model",
        )
        session.add(call)

        tag = SubSegmentTag(
            run_id=run.id,
            chapter_id=chapter.id,
            segment_id=segment.id,
            sub_segment_id="segment-1",
            sub_segment_index=0,
            shift_type="emotion",
            boundary_start_char=0,
            boundary_end_char=5,
            confidence=1.0,
            tags={"emotion": "calm"},
            evidence={"source": "mock"},
            from_label="neutral",
            to_label="neutral",
            from_text="Nova",
            to_text="Nova",
        )
        session.add(tag)

        blob = RunNormalizedCorpusBlob(
            run_id=run.id,
            source="pipeline",
            source_filename=None,
            corpus_sha256="0" * 64,
            normalized_corpus_blob=b"nova spoke",
        )
        session.add(blob)

        raw_corpus = "Nova spoke."
        raw_corpus_blob = ProjectRawCorpusBlob(
            project_id=project_id,
            source="fixture",
            source_filename=None,
            blob_sha256=sha256(raw_corpus.encode("utf-8")).hexdigest(),
            raw_corpus_blob=raw_corpus.encode("utf-8"),
        )
        session.add(raw_corpus_blob)

        run_configuration_snapshot = RunConfigurationSnapshot(
            project_id=project_id,
            run_id=run.id,
            version=1,
            source="test_fixture",
            snapshot_json={
                "project_id": project_id,
                "run_id": run.id,
                "mode": "academic",
                "configuration_snapshot_id": f"run-{run.id}-config-1",
                "configuration": {"mode": "academic"},
            },
            snapshot_json_sha256="",
        )
        run_configuration_snapshot.snapshot_json_sha256 = _build_snapshot_json_checksum(run_configuration_snapshot.snapshot_json)
        session.add(run_configuration_snapshot)

        character_map_snapshot = CharacterMapSnapshot(
            project_id=project_id,
            run_id=run.id,
            version=1,
            source="test_fixture",
            snapshot_json={"character_count": 0, "characters": []},
            snapshot_json_sha256="",
        )
        character_map_snapshot.snapshot_json_sha256 = _build_snapshot_json_checksum(character_map_snapshot.snapshot_json)
        session.add(character_map_snapshot)

        pronunciation_dictionary_snapshot = PronunciationDictionarySnapshot(
            project_id=project_id,
            run_id=run.id,
            version=1,
            source="test_fixture",
            snapshot_json={"entry_count": 0, "by_scope": {"global": [], "place": [], "character": []}},
            snapshot_json_sha256="",
        )
        pronunciation_dictionary_snapshot.snapshot_json_sha256 = _build_snapshot_json_checksum(
            pronunciation_dictionary_snapshot.snapshot_json
        )
        session.add(pronunciation_dictionary_snapshot)

        voice_map_snapshot = VoiceMapSnapshot(
            project_id=project_id,
            run_id=run.id,
            version=1,
            source="test_fixture",
            snapshot_json={"character_voice_map_count": 0, "by_character": {}},
            snapshot_json_sha256="",
        )
        voice_map_snapshot.snapshot_json_sha256 = _build_snapshot_json_checksum(voice_map_snapshot.snapshot_json)
        session.add(voice_map_snapshot)
        session.flush()
        run.config_json = {
            **run.config_json,
            "configuration_snapshot_id": run_configuration_snapshot.id,
            "configuration_snapshot_version": run_configuration_snapshot.version,
            "character_map_snapshot_id": character_map_snapshot.id,
            "character_map_snapshot_version": character_map_snapshot.version,
            "pronunciation_dictionary_snapshot_id": pronunciation_dictionary_snapshot.id,
            "pronunciation_dictionary_snapshot_version": pronunciation_dictionary_snapshot.version,
            "voice_map_snapshot_id": voice_map_snapshot.id,
            "voice_map_snapshot_version": voice_map_snapshot.version,
        }
        session.add(run)

        # time series snapshot is intentionally omitted until post-recovery pipeline completion.
        session.commit()
        return run.id
    finally:
        session.close()


def test_recover_run_refreshes_stale_artifacts_and_completes(
    monkeypatch,
) -> None:
    project_id = _create_project()
    run_id = _create_stale_run_with_artifacts(
        project_id=project_id,
        status="running",
        stale_minutes=15,
        pipeline_recovery={
            "status": "failed",
            "attempt": 1,
            "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
            "reason": "pipeline_error",
        },
    )

    def _mock_pipeline(*, session, project, run, run_config):
        assert project.id == project_id
        assert run_id == run.id
        assert run_config["pipeline_recovery"]["status"] == "running"
        normalized_text = "Nova spoke."
        session.add(
            RunNormalizedCorpusBlob(
                run_id=run.id,
                source="pipeline",
                source_filename=None,
                corpus_sha256=sha256(normalized_text.encode("utf-8")).hexdigest(),
                normalized_corpus_blob=normalized_text.encode("utf-8"),
            )
        )
        return {
            "segment_count": 4,
            "export": {"time_series": {"emotion_valence": [0.3, 0.4]}},
        }

    monkeypatch.setattr("app.main.execute_pipeline", _mock_pipeline)

    with TestClient(app) as client:
        recover_resp = client.post(f"/api/projects/{project_id}/runs/{run_id}/recover")

    assert recover_resp.status_code == 200
    payload = recover_resp.json()
    assert payload["status"] == "completed"
    assert payload["segment_count"] == 4

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        assert run.status == "completed"
        assert isinstance(run.config_json, dict)
        recovery_state = run.config_json.get("pipeline_recovery")
        assert isinstance(recovery_state, dict)
        assert recovery_state["status"] == "completed"
        assert recovery_state["attempt"] == 2
        assert recovery_state["reason"] == "manual_recovery"

        assert session.query(LLMCall).filter(LLMCall.run_id == run_id).count() == 0
        assert session.query(Segment).filter(Segment.run_id == run_id).count() == 0
        assert session.query(SubSegmentTag).filter(SubSegmentTag.run_id == run_id).count() == 0
        assert session.query(RunNormalizedCorpusBlob).filter(RunNormalizedCorpusBlob.run_id == run_id).count() == 1

        events = (
            session.query(RunChangelogEntry)
            .filter(RunChangelogEntry.run_id == run_id)
            .order_by(RunChangelogEntry.id.asc())
            .all()
        )
        event_types = [entry.event_type for entry in events]
        assert event_types[-1] == "pipeline_completed"
        assert "pipeline_recovery_requested" in event_types
    finally:
        session.close()


def test_recover_run_rejects_non_stale_running_job() -> None:
    project_id = _create_project()
    run_id = _create_stale_run_with_artifacts(
        project_id=project_id,
        status="running",
        stale_minutes=0.1,
        pipeline_recovery=None,
    )

    with TestClient(app) as client:
        recover_resp = client.post(f"/api/projects/{project_id}/runs/{run_id}/recover")

    assert recover_resp.status_code == 409
    assert recover_resp.json()["detail"] == "Run is not yet eligible for recovery."
