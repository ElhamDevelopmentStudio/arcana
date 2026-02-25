import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingestion_encoding.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import decode_text, detect_text_encoding


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingestion_encoding.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_detect_text_encoding_identifies_utf8() -> None:
    encoding, confidence = detect_text_encoding("Shadow Slave".encode("utf-8"))
    assert encoding == "utf-8"
    assert confidence >= 0.9


def test_integration_detect_text_encoding_identifies_utf16_bom() -> None:
    payload = "Shadow Slave".encode("utf-16-le")
    payload = b"\xff\xfe" + payload
    encoding, confidence = detect_text_encoding(payload)
    assert encoding == "utf-16-le"
    assert confidence == 1.0


def test_e2e_ingest_txt_decodes_cp1252_input_via_detection() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Encoding Detection E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        cp1252_text = "Chapter 1\nCafe café scene."
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("cp1252.txt", io.BytesIO(cp1252_text.encode("cp1252")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        chapter = session.query(Chapter).filter(Chapter.project_id == project_id).one()
        assert "café" in chapter.raw_text
    finally:
        session.close()


def test_regression_decode_text_never_raises_on_binary_noise() -> None:
    noisy = b"\xff\xfe\xfa\xfb\x00\x01binary"
    decoded = decode_text(noisy)
    assert isinstance(decoded, str)
    assert len(decoded) > 0
