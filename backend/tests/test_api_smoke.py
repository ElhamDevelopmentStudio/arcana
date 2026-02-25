import io
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipc_poc.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Segment
from app.services.segment_reconstruction import reconstruct_chapter_text_from_segments, reconstruct_corpus_from_chapter_artifacts


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    test_db = Path("test_nipc_poc.db")
    if test_db.exists():
        test_db.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _sample_characters_json() -> bytes:
    payload = {
        "Sunny": {"verbalized_form": "Sunny", "gender": "male"},
        "Nephis": {"verbalized_form": "Ne-fis", "gender": "female"},
    }
    return json.dumps(payload).encode("utf-8")


def _segmentation_metadata_text() -> str:
    chapter_text = (
        "Every character in this story speaks briefly as the night wind rises. "
        "The road was wet with rain and every lamp cast long trembling shadows. "
        "A few minutes felt like hours inside the narrow silence. "
    )
    return "Chapter 1\n" + chapter_text + chapter_text + "\n\n" + "Chapter 2\n" + chapter_text + chapter_text


def test_full_poc_api_flow_deterministic_export() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Shadow Slave PoC"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        assert project_resp.json()["selected_mode"] == "audiobook"
        assert project_resp.json()["selected_modes"] == ["audiobook"]
        assert project_resp.json()["configuration_snapshot_id"] == f"project-{project_id}-config-initial"

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        char_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(_sample_characters_json()), "application/json")},
        )
        assert char_resp.status_code == 200
        assert char_resp.json()["imported_count"] == 2

        voice_resp = client.put(
            f"/api/projects/{project_id}/voices",
            json={
                "narrator_voice": "narrator_default",
                "male_default_voice": "male_default",
                "female_default_voice": "female_default",
            },
        )
        assert voice_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 120,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
            "allow_unfinalized_character_map": True,
        }

        run_resp_1 = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp_1.status_code == 200
        run_id_1 = run_resp_1.json()["run_id"]

        run_detail_1 = client.get(f"/api/projects/{project_id}/runs/{run_id_1}")
        assert run_detail_1.status_code == 200
        assert run_detail_1.json()["config"]["mode"] == "audiobook"

        export_1 = client.get(f"/api/projects/{project_id}/exports/{run_id_1}.json")
        assert export_1.status_code == 200
        data_1 = export_1.json()

        assert data_1["segments"]
        for segment in data_1["segments"]:
            assert len(segment["original_text"]) <= 120
            assert set(
                [
                    "chapter_id",
                    "segment_id",
                    "original_text",
                    "phonetic_text",
                    "type",
                    "speaker",
                    "gender",
                    "voice_id",
                    "emotion_valence",
                    "emotion_intensity",
                    "confidence",
                ]
            ).issubset(segment.keys())
            assert set(segment["confidence"].keys()).issuperset(
                {"speaker", "emotion", "gender", "type", "tension", "dominance"}
            )

        run_resp_2 = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp_2.status_code == 200
        run_id_2 = run_resp_2.json()["run_id"]

        export_2 = client.get(f"/api/projects/{project_id}/exports/{run_id_2}.json")
        assert export_2.status_code == 200
        data_2 = export_2.json()

        assert data_1["segments"] == data_2["segments"]


def test_integration_export_segments_include_chapter_id_metadata() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Segment Chapter Metadata"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_segmentation_metadata_text().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        segments = export_resp.json()["segments"]
        assert segments

        chapter_ids = {segment["chapter_id"] for segment in segments}
        chapter_segment_indexes: dict[int, list[int]] = {chapter_id: [] for chapter_id in chapter_ids}

        assert chapter_ids == {1, 2}
        assert all(isinstance(segment["chapter_id"], int) for segment in segments)
        assert all(segment["chapter_id"] in {1, 2} for segment in segments)
        assert all(segment.get("chapter_internal_id") in {"ch-0001", "ch-0002"} for segment in segments)
        assert all(segment.get("chapter_internal_id", "").startswith("ch-") for segment in segments)
        assert all("segment_index" in segment for segment in segments)
        assert all(isinstance(segment["segment_index"], int) for segment in segments)
        assert all("original_span_pointer" in segment for segment in segments)
        assert all(
            isinstance(segment["original_span_pointer"], dict) and
            isinstance(segment["original_span_pointer"]["original_start_char"], int) and
            isinstance(segment["original_span_pointer"]["original_end_char"], int) and
            isinstance(segment["original_span_pointer"]["normalized_start_char"], int) and
            isinstance(segment["original_span_pointer"]["normalized_end_char"], int)
            for segment in segments
        )
        assert all("parent_paragraph_reference" in segment for segment in segments)
        assert all(
            isinstance(segment["parent_paragraph_reference"], dict)
            and isinstance(segment["parent_paragraph_reference"].get("paragraph_index"), int)
            and isinstance(segment["parent_paragraph_reference"].get("paragraph_id"), str)
            for segment in segments
        )
        assert all("parent_sentence_reference" in segment for segment in segments)
        assert all(
            isinstance(segment["parent_sentence_reference"], dict)
            and isinstance(segment["parent_sentence_reference"].get("sentence_start_index"), int)
            and isinstance(segment["parent_sentence_reference"].get("sentence_end_index"), int)
            and isinstance(segment["parent_sentence_reference"].get("sentence_id"), str)
            for segment in segments
        )
        assert all("normalized_text" in segment for segment in segments)
        assert all(isinstance(segment["normalized_text"], str) for segment in segments)
        assert all(segment["normalized_text"] == segment["original_text"] for segment in segments)
        assert all(
            segment["original_span_pointer"]["normalized_end_char"]
            >= segment["original_span_pointer"]["normalized_start_char"]
            for segment in segments
        )

        for segment in segments:
            chapter_segment_indexes[segment["chapter_id"]].append(segment["segment_index"])

        for _, segment_indexes in chapter_segment_indexes.items():
            assert segment_indexes == list(range(1, len(segment_indexes) + 1))


def test_integration_round_trip_reconstruction_audit_matches_normalized_text() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Reconstruction Audit"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_segmentation_metadata_text().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        session = get_session_factory()()
        try:
            chapters = (
                session.query(Chapter)
                .filter(Chapter.project_id == project_id)
                .order_by(Chapter.chapter_index.asc())
                .all()
            )
            segment_rows = (
                session.query(Segment)
                .filter(Segment.run_id == run_id)
                .order_by(Segment.id.asc())
                .all()
            )

            assert len(chapters) == 2
            assert len(segment_rows) > 0

            segments_by_chapter: dict[int, list[dict]] = {}
            for segment in segment_rows:
                payload = segment.segment_json
                if not isinstance(payload, dict):
                    payload = {}
                segments_by_chapter.setdefault(segment.chapter_id, []).append(payload)

            reconstructed_chapters = []
            chapter_artifacts = []
            for chapter in chapters:
                assert chapter.id in segments_by_chapter
                reconstructed = reconstruct_chapter_text_from_segments(
                    chapter.normalized_text,
                    segments_by_chapter[chapter.id],
                )
                assert reconstructed == chapter.normalized_text
                reconstructed_chapters.append(reconstructed)
                chapter_artifacts.append(
                    {
                        "chapter_index": chapter.chapter_index,
                        "normalized_text": chapter.normalized_text,
                        "segment_payloads": segments_by_chapter[chapter.id],
                    }
                )

            reconstructed_corpus = reconstruct_corpus_from_chapter_artifacts(chapter_artifacts)
            expected_corpus = "\n\n".join(reconstructed_chapters)
            assert reconstructed_corpus == expected_corpus
        finally:
            session.close()
