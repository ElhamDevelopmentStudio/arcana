import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_tag_bundle_and_confidence.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_export_tag_bundle_and_confidence.db")
    if db_file.exists():
        db_file.unlink()


def test_export_includes_per_segment_tag_bundle_and_confidence() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "Tag Bundle Export"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        b'Chapter 1\n"Stay calm," Ally said. She glanced up, then whispered, "It\'s almost dawn."'
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        update_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Ally",
                        "verbalized_form": "Ally",
                        "gender": "female",
                        "aliases": ["Ally", "She"],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 1.0,
                        "inferred_source_trace": [],
                    }
                ]
            },
        )
        assert update_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True, "max_segment_chars": 140},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

        payload = export_resp.json()
        segments = payload["segments"]
        assert segments

        for segment in segments:
            tag_bundle = segment["tag_bundle"]
            assert isinstance(tag_bundle, dict)
            assert tag_bundle.get("type") == segment["type"]
            assert tag_bundle.get("speaker") == segment["speaker"]
            assert tag_bundle.get("speaker_id") == segment.get("speaker_id")
            assert tag_bundle.get("gender") == segment["gender"]

            segment_confidence = segment["confidence"]
            bundle_confidence = tag_bundle["confidence"]
            assert isinstance(segment_confidence, dict)
            assert isinstance(bundle_confidence, dict)
            assert bundle_confidence == segment_confidence

            assert tag_bundle.get("type_confidence") == segment_confidence["type"]
            assert tag_bundle.get("speaker_confidence") == segment_confidence["speaker"]
            assert "emotion" in tag_bundle and isinstance(tag_bundle["emotion"], dict)
            assert "valence" in tag_bundle["emotion"]
            assert "intensity" in tag_bundle["emotion"]
            assert "primary_label" in tag_bundle["emotion"]
            assert tag_bundle["emotion"]["confidence"] == segment_confidence["emotion"]
            assert "evidence" in tag_bundle["emotion"]

            assert "tension" in tag_bundle and isinstance(tag_bundle["tension"], dict)
            assert "dominance" in tag_bundle and isinstance(tag_bundle["dominance"], dict)
            assert "summary_tag" in tag_bundle
