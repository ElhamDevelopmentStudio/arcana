import io
import os
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingestion_error_types.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.services.ingestion_errors import (
    IngestionErrorType,
    IngestionInProgressError,
    UnsupportedEncodingIngestionError,
    MissingChaptersIngestionError,
    UnsupportedFormatIngestionError,
    make_ingestion_http_error,
)


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingestion_error_types.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient, title: str) -> int:
    response = client.post("/api/projects", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


def test_unit_make_ingestion_http_error_sets_error_type_header() -> None:
    error = make_ingestion_http_error(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_type=IngestionErrorType.UNSUPPORTED_FORMAT,
        detail="Only .txt files are supported",
    )
    assert error.status_code == 400
    assert error.headers == {"X-NIPE-Error-Type": "unsupported_format"}
    assert error.detail == "Only .txt files are supported"


def test_unit_unsupported_format_error_is_http_exception_with_header() -> None:
    error = UnsupportedFormatIngestionError(detail="Only .txt files are supported")
    assert error.status_code == 400
    assert error.headers == {"X-NIPE-Error-Type": "unsupported_format"}
    assert error.detail == "Only .txt files are supported"


def test_unit_unsupported_encoding_error_is_http_exception_with_header() -> None:
    error = UnsupportedEncodingIngestionError(detail="Unable to decode TXT content reliably with supported encodings")
    assert error.status_code == 400
    assert error.headers == {"X-NIPE-Error-Type": "unsupported_encoding"}
    assert error.detail == "Unable to decode TXT content reliably with supported encodings"


def test_unit_missing_chapters_error_is_http_exception_with_header() -> None:
    error = MissingChaptersIngestionError(detail="No non-empty chapters found in TXT input")
    assert error.status_code == 400
    assert error.headers == {"X-NIPE-Error-Type": "missing_chapters"}
    assert error.detail == "No non-empty chapters found in TXT input"


def test_unit_ingestion_in_progress_error_is_http_exception_with_header() -> None:
    error = IngestionInProgressError(
        detail="Ingestion is already running for this project. Wait for completion before uploading again.",
    )
    assert error.status_code == 409
    assert error.headers == {"X-NIPE-Error-Type": "in_progress"}
    assert error.detail == "Ingestion is already running for this project. Wait for completion before uploading again."


def test_integration_unsupported_format_sets_error_type_header() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client, "Ingestion Error Type Integration")
        response = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.md", io.BytesIO(b"# not txt"), "text/markdown")},
        )
        assert response.status_code == 400
        assert response.headers["x-nipe-error-type"] == "unsupported_format"
        assert response.json()["detail"] == "Only .txt files are supported"


def test_e2e_missing_chapters_sets_error_type_header() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client, "Ingestion Error Type E2E")
        response = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"   \n  \n"), "text/plain")},
        )
        assert response.status_code == 400
        assert response.headers["x-nipe-error-type"] == "missing_chapters"
        assert "requires exactly one non-empty chapter" in response.json()["detail"]


def test_regression_unsupported_encoding_sets_error_type_header() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client, "Ingestion Error Type Regression")
        utf16_without_bom = ("Chapter 1\n" + ("Bad decode sample " * 20)).encode("utf-16-le")
        response = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("weird.txt", io.BytesIO(utf16_without_bom), "text/plain")},
        )
        assert response.status_code == 400
        assert response.headers["x-nipe-error-type"] == "unsupported_encoding"
        assert response.json()["detail"] == "Unable to decode TXT content reliably with supported encodings"


def test_integration_ingestion_in_progress_sets_error_type_header(monkeypatch) -> None:
    def _raise_in_progress(*_: object, **__: object) -> None:
        raise IngestionInProgressError(
            detail="Ingestion is already running for this project. Wait for completion before uploading again.",
        )

    monkeypatch.setattr("app.main._lock_project_for_ingestion", _raise_in_progress)

    with TestClient(app) as client:
        project_id = _create_project(client, "Ingestion In Progress Header Integration")
        response = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\ntext"), "text/plain")},
        )
        assert response.status_code == 409
        assert response.headers["x-nipe-error-type"] == "in_progress"
        assert response.json()["detail"] == (
            "Ingestion is already running for this project. Wait for completion before uploading again."
        )
