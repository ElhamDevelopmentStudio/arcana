import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acad_workspace.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_acad_workspace.db")
    if db_file.exists():
        db_file.unlink()


def _sample_novel() -> bytes:
    return (
        "Chapter 1\n"
        "The wind pressed at the shutters and the room felt too small for quiet thoughts.\n\n"
        "Chapter 2\n"
        "She set the lamp beside the map and studied every line until dawn touched the glass."
    ).encode("utf-8")


def _create_ingested_project(client: TestClient, title: str) -> int:
    create_resp = client.post("/api/projects", json={"title": title})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(_sample_novel()), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] >= 1
    return project_id


def _run_project(client: TestClient, project_id: int) -> int:
    run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 120})
    assert run_resp.status_code == 200
    payload = run_resp.json()
    assert payload["run_id"] > 0
    return int(payload["run_id"])


def _create_ingested_project_with_text(client: TestClient, title: str, text: str) -> int:
    create_resp = client.post("/api/projects", json={"title": title})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] >= 1
    return project_id


def _fixture_text(filename: str) -> str:
    text = (FIXTURES_DIR / filename).read_text(encoding="utf-8").strip()
    assert text
    return text


def test_create_comparison_workspace() -> None:
    with TestClient(app) as client:
        create_response = client.post(
            "/api/comparison-workspaces",
            json={"name": "Workspace ACAD-016"},
        )
        assert create_response.status_code == 201
        payload = create_response.json()
        assert payload["workspace_id"] > 0
        assert payload["name"] == "Workspace ACAD-016"
        assert payload["run_count"] == 0
        assert payload["runs"] == []


def test_add_runs_to_comparison_workspace_and_readback() -> None:
    with TestClient(app) as client:
        project_one = _create_ingested_project(client, "Novel One")
        project_two = _create_ingested_project(client, "Novel Two")
        run_one = _run_project(client, project_one)
        run_two = _run_project(client, project_two)

        create_response = client.post("/api/comparison-workspaces", json={"name": "Workspace ACAD-016 Compare"})
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        add_one_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_one, "run_id": run_one},
        )
        assert add_one_response.status_code == 201
        workspace_payload = add_one_response.json()
        assert workspace_payload["run_count"] == 1
        assert len(workspace_payload["runs"]) == 1

        add_two_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_two, "run_id": run_two},
        )
        assert add_two_response.status_code == 201
        workspace_payload = add_two_response.json()
        assert workspace_payload["run_count"] == 2
        assert len(workspace_payload["runs"]) == 2

        run_ids = {run["run_id"] for run in workspace_payload["runs"]}
        assert run_ids == {run_one, run_two}

        get_response = client.get(f"/api/comparison-workspaces/{workspace_id}")
        assert get_response.status_code == 200
        get_payload = get_response.json()
        assert get_payload["run_count"] == 2
        assert get_payload["runs"][0]["project_id"] in {project_one, project_two}
        assert get_payload["runs"][1]["project_id"] in {project_one, project_two}


def test_prevent_duplicate_or_invalid_run_assignment() -> None:
    with TestClient(app) as client:
        project_one = _create_ingested_project(client, "Novel Duplicate")
        run_one = _run_project(client, project_one)

        create_response = client.post("/api/comparison-workspaces", json={"name": "Workspace ACAD-016 Duplicate"})
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        first_add_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_one, "run_id": run_one},
        )
        assert first_add_response.status_code == 201

        duplicate_add_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_one, "run_id": run_one},
        )
        assert duplicate_add_response.status_code == 409

        mismatch_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_one + 1, "run_id": run_one},
        )
        assert mismatch_response.status_code == 404


def test_get_aligned_comparison_curves_for_workspace() -> None:
    short_novel = (
        "Chapter 1\n"
        "A brief chapter with a few lines.\n\n"
        "Chapter 2\n"
        "Another short chapter settles quickly."
    )
    long_novel = (
        "Chapter 1\n"
        "A more elaborate chapter with many details and emotional turns.\n"
        "The rain came harder, and shadows moved across the wall.\n"
        "Each corridor echoed with uncertain echoes.\n\n"
        "Chapter 2\n"
        "Later, in the long library, the voice returned to warmth.\n"
        "By evening, the pace had shifted.\n"
    )

    with TestClient(app) as client:
        project_one = _create_ingested_project_with_text(client, "Aligned One", short_novel)
        project_two = _create_ingested_project_with_text(client, "Aligned Two", long_novel)

        run_one = _run_project(client, project_one)
        run_two = _run_project(client, project_two)

        create_response = client.post("/api/comparison-workspaces", json={"name": "Workspace ACAD-017"})
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        add_one_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_one, "run_id": run_one},
        )
        assert add_one_response.status_code == 201
        add_two_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_two, "run_id": run_two},
        )
        assert add_two_response.status_code == 201

        curves_response = client.get(f"/api/comparison-workspaces/{workspace_id}/aligned-curves")
        assert curves_response.status_code == 200
        payload = curves_response.json()

        assert payload["workspace_id"] == workspace_id
        assert payload["run_count"] == 2
        assert payload["aligned_points"] == 32
        metrics = payload["metrics"]
        assert len(metrics) == 7

        metric_ids = {metric["metric_id"] for metric in metrics}
        assert metric_ids == {
            "chapter_valence_mean",
            "chapter_valence_variance",
            "chapter_emotional_volatility",
            "smoothed_tension_curve",
            "rolling_valence_curve",
            "rolling_intensity_curve",
            "normalized_pacing_signature",
        }

        for metric in metrics:
            assert len(metric["points_per_run"]) == 2
            for run_descriptor in metric["points_per_run"]:
                assert len(run_descriptor["points"]) == 32
                normalized_positions = [point["normalized_position"] for point in run_descriptor["points"]]
                assert normalized_positions[0] == 0.0
                assert normalized_positions[-1] == 1.0
                if metric["metric_id"] == "normalized_pacing_signature":
                    assert all(0.0 <= point["value"] <= 1.0 for point in run_descriptor["points"])


def test_get_aligned_curves_with_filter_and_alignment() -> None:
    with TestClient(app) as client:
        project = _create_ingested_project(client, "Aligned Metrics")
        run_id = _run_project(client, project)
        create_response = client.post("/api/comparison-workspaces", json={"name": "Workspace ACAD-017 Filter"})
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        link_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project, "run_id": run_id},
        )
        assert link_response.status_code == 201

        metrics_filter = "chapter_valence_mean,smoothed_tension_curve,normalized_pacing_signature"
        filtered_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/aligned-curves?metrics={metrics_filter}&aligned_points=7"
        )
        assert filtered_response.status_code == 200
        filtered_payload = filtered_response.json()
        assert filtered_payload["run_count"] == 1
        assert filtered_payload["aligned_points"] == 7
        assert {metric["metric_id"] for metric in filtered_payload["metrics"]} == set(metrics_filter.split(","))

        for metric in filtered_payload["metrics"]:
            assert len(metric["points_per_run"]) == 1
            assert len(metric["points_per_run"][0]["points"]) == 7

        invalid_metric_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/aligned-curves?metrics=nonexistent_metric"
        )
        assert invalid_metric_response.status_code == 422


def test_aligned_curves_rejects_invalid_aligned_points() -> None:
    with TestClient(app) as client:
        project = _create_ingested_project(client, "Aligned Bounds")
        run_id = _run_project(client, project)
        create_response = client.post("/api/comparison-workspaces", json={"name": "Workspace ACAD-017 Bounds"})
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        link_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project, "run_id": run_id},
        )
        assert link_response.status_code == 201

        too_few_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/aligned-curves?aligned_points=1"
        )
        assert too_few_response.status_code == 400

        too_many_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/aligned-curves?aligned_points=401"
        )
        assert too_many_response.status_code == 400


def test_export_comparative_dataset_for_workspace() -> None:
    short_novel = (
        "Chapter 1\n"
        "The gate opened slowly.\n\n"
        "Chapter 2\n"
        "Clouds moved over the hill and the room held its breath."
    )
    long_novel = (
        "Chapter 1\n"
        "This chapter opens with many subtle emotional turns.\n"
        "The air was stale and bright with unease.\n\n"
        "Chapter 2\n"
        "Later, footsteps echoed against the wall while the argument deepened.\n"
        "A soft laugh cut through the storm.\n\n"
        "Chapter 3\n"
        "By night, the pace accelerated.\n"
        "Then, too quickly, everything stilled."
    )

    with TestClient(app) as client:
        project_one = _create_ingested_project_with_text(client, "Comparative Dataset One", short_novel)
        project_two = _create_ingested_project_with_text(client, "Comparative Dataset Two", long_novel)
        run_one = _run_project(client, project_one)
        run_two = _run_project(client, project_two)

        create_response = client.post(
            "/api/comparison-workspaces",
            json={"name": "Workspace ACAD-019"},
        )
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        link_one_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_one, "run_id": run_one},
        )
        assert link_one_response.status_code == 201
        link_two_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_two, "run_id": run_two},
        )
        assert link_two_response.status_code == 201

        export_response = client.get(f"/api/comparison-workspaces/{workspace_id}/exports/comparative-dataset.json")
        assert export_response.status_code == 200
        payload = export_response.json()
        assert payload["workspace_id"] == workspace_id
        assert payload["run_count"] == 2
        assert payload["aligned_points"] == 32
        assert payload["workspace_name"] == "Workspace ACAD-019"
        assert "generated_at" in payload
        assert payload["generated_at"] is not None

        assert isinstance(payload["metrics"], list)
        assert len(payload["metrics"]) == 7
        for metric in payload["metrics"]:
            assert len(metric["points_per_run"]) == 2
            for run_descriptor in metric["points_per_run"]:
                assert run_descriptor["run_id"] in {run_one, run_two}
                assert len(run_descriptor["points"]) == 32

        assert isinstance(payload["runs"], list)
        assert len(payload["runs"]) == 2
        run_identifiers = {run["run_id"] for run in payload["runs"]}
        assert run_identifiers == {run_one, run_two}
        for run in payload["runs"]:
            assert "academic_reports" in run
            assert "comparative_run_metrics_snapshot" in run
            assert "academic_export_manifest" in run
            assert "segment_count" in run


def test_export_comparative_dataset_supports_metric_filter_and_validation() -> None:
    with TestClient(app) as client:
        project_one = _create_ingested_project(client, "Comparative Filter")
        run_one = _run_project(client, project_one)

        create_response = client.post(
            "/api/comparison-workspaces",
            json={"name": "Workspace ACAD-019 Filter"},
        )
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        add_run_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": project_one, "run_id": run_one},
        )
        assert add_run_response.status_code == 201

        filtered_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/exports/comparative-dataset.json"
            "?metrics=chapter_valence_mean,smoothed_tension_curve,normalized_pacing_signature&aligned_points=9"
        )
        assert filtered_response.status_code == 200
        filtered_payload = filtered_response.json()
        assert filtered_payload["aligned_points"] == 9
        assert filtered_payload["run_count"] == 1
        assert {metric["metric_id"] for metric in filtered_payload["metrics"]} == {
            "chapter_valence_mean",
            "smoothed_tension_curve",
            "normalized_pacing_signature",
        }
        for metric in filtered_payload["metrics"]:
            assert len(metric["points_per_run"][0]["points"]) == 9

        invalid_metric_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/exports/comparative-dataset.json?metrics=bad_metric"
        )
        assert invalid_metric_response.status_code == 422

        invalid_bound_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/exports/comparative-dataset.json?aligned_points=401"
        )
        assert invalid_bound_response.status_code == 400


def test_comparative_dataset_verifies_differences_across_two_corpora() -> None:
    with TestClient(app) as client:
        corpus_one_project = _create_ingested_project_with_text(
            client,
            "Rapid Emotion Corpus",
            _fixture_text("rapid_emotional_shifts.txt"),
        )
        corpus_two_project = _create_ingested_project_with_text(
            client,
            "Mixed Narration Corpus",
            _fixture_text("mixed_narration_dialogue_segment.txt"),
        )
        corpus_one_run = _run_project(client, corpus_one_project)
        corpus_two_run = _run_project(client, corpus_two_project)

        create_response = client.post(
            "/api/comparison-workspaces",
            json={"name": "Workspace ACAD-020"},
        )
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        add_one_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": corpus_one_project, "run_id": corpus_one_run},
        )
        assert add_one_response.status_code == 201
        add_two_response = client.post(
            f"/api/comparison-workspaces/{workspace_id}/runs",
            json={"project_id": corpus_two_project, "run_id": corpus_two_run},
        )
        assert add_two_response.status_code == 201

        export_response = client.get(
            f"/api/comparison-workspaces/{workspace_id}/exports/comparative-dataset.json?aligned_points=8"
        )
        assert export_response.status_code == 200
        payload = export_response.json()
        assert payload["run_count"] == 2
        assert payload["aligned_points"] == 8
        assert isinstance(payload["metrics"], list)
        assert len(payload["metrics"]) == 7

        points_per_run_by_metric = {
            metric["metric_id"]: {
                run_descriptor["run_id"]: [point["value"] for point in run_descriptor["points"]]
                for run_descriptor in metric["points_per_run"]
            }
            for metric in payload["metrics"]
        }
        assert points_per_run_by_metric["chapter_valence_mean"][corpus_one_run] != points_per_run_by_metric["chapter_valence_mean"][
            corpus_two_run
        ]
        assert points_per_run_by_metric["smoothed_tension_curve"][corpus_one_run] != points_per_run_by_metric["smoothed_tension_curve"][
            corpus_two_run
        ]

        metric_norm_sig = points_per_run_by_metric["normalized_pacing_signature"]
        assert all(0.0 <= value <= 1.0 for run_points in metric_norm_sig.values() for value in run_points)

        runs = payload["runs"]
        assert len(runs) == 2
        run_segment_counts = {run["run_id"]: run["segment_count"] for run in runs}
        assert run_segment_counts[corpus_one_run] > 0
        assert run_segment_counts[corpus_two_run] > 0
        assert run_segment_counts[corpus_one_run] != run_segment_counts[corpus_two_run]

        for run in runs:
            assert "academic_export_manifest" in run
            assert "comparative_run_metrics_snapshot" in run
            assert "academic_reports" in run
