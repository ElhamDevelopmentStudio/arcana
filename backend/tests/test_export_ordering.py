import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_ordering.db"

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

    db_file = Path("test_nipe_export_ordering.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient) -> int:
    project_resp = client.post("/api/projects", json={"title": "Ordered Corpus Export"})
    assert project_resp.status_code == 201
    return project_resp.json()["id"]


def _ingest_text(client: TestClient, project_id: int) -> None:
    payload = (
        "Chapter 1\n"
        "First a spark lit the alley, and then the bell echoed through the fog.\n\n"
        "Second breath rose as the crowd gathered near the market.\n\n"
        "Chapter 2\n"
        "Lanterns lined the avenue. The first watch changed. Footsteps clicked behind us.\n\n"
        "Second wind arrived and the story moved onward."
    )
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("ordered.txt", io.BytesIO(payload.encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] == 2


def _run_collision_scope_case(client: TestClient, character_rows: list[tuple[str, str]]) -> str:
    project_id = _create_project(client)

    collision_payload = (
        'Chapter 1\n'
        '"signal," kai said.\n'
    )
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("collision.txt", io.BytesIO(collision_payload.encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] == 1

    character_payload = {
        "characters": [
            {
                "name": name,
                "verbalized_form": name,
                "gender": "female",
                "aliases": [],
            }
            for name, _ in character_rows
        ]
    }
    character_resp = client.put(f"/api/projects/{project_id}/characters", json=character_payload)
    assert character_resp.status_code == 200

    for name, verbalized in character_rows:
        dictionary_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/{name}",
            json={"entries": [{"term": "signal", "verbalized_form": verbalized}]},
        )
        assert dictionary_resp.status_code == 200

    run_payload = {
        "max_segment_chars": 255,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 2,
        "allow_unfinalized_character_map": True,
    }
    run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200
    payload = export_resp.json()
    return payload["segments"][0]["phonetic_text"]


def test_export_segments_are_ordered_across_chapters_then_segments() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client)
        _ingest_text(client, project_id)

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

        payload = export_resp.json()
        segments = payload["segments"]
        assert payload["status"] == "completed"
        assert segments

        ordered_keys = [
            (int(segment["chapter_id"]), int(segment["segment_index"])) for segment in segments
        ]
        assert ordered_keys == sorted(ordered_keys)

        seen_segment_ids: set[str] = set()
        ordered_by_chapter: dict[int, list[int]] = {}
        for segment in segments:
            segment_id = segment.get("segment_id")
            assert segment_id is not None
            segment_id_str = str(segment_id)
            assert segment_id_str not in seen_segment_ids
            seen_segment_ids.add(segment_id_str)

            chapter_id = int(segment["chapter_id"])
            ordered_by_chapter.setdefault(chapter_id, []).append(int(segment["segment_index"]))

        for segment_indexes in ordered_by_chapter.values():
            assert segment_indexes == list(range(1, len(segment_indexes) + 1))


def test_pipeline_character_scope_lookup_is_deterministic_with_normalized_name_collisions() -> None:
    with TestClient(app) as client:
        forward_phonetic = _run_collision_scope_case(
            client,
            character_rows=[("Kai", "alpha-signal"), ("kai", "beta-signal")],
        )
        reverse_phonetic = _run_collision_scope_case(
            client,
            character_rows=[("kai", "beta-signal"), ("Kai", "alpha-signal")],
        )

        assert forward_phonetic == reverse_phonetic
        assert ("alpha-signal" in forward_phonetic) or ("beta-signal" in forward_phonetic)
