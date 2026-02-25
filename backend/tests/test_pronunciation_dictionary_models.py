import os
from pathlib import Path

from sqlalchemy.exc import IntegrityError
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_nipv_pronunciation_dictionary.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.models import PronunciationDictionary, Project


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipv_pronunciation_dictionary.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_pronunciation_dictionary_global_terms_can_be_created() -> None:
    session = get_session_factory()()
    try:
        project = Project(title="Pronunciation Dictionary")
        session.add(project)
        session.flush()

        entry = PronunciationDictionary(
            project_id=project.id,
            scope="global",
            character_name="",
            term="Aegis",
            verbalized_form="EE-jis",
            source="user_import",
            confidence=1.0,
        )
        session.add(entry)
        session.commit()

        persisted = (
            session.query(PronunciationDictionary)
            .filter(
                PronunciationDictionary.project_id == project.id,
                PronunciationDictionary.scope == "global",
                PronunciationDictionary.term == "Aegis",
            )
            .one()
        )
        assert persisted.scope == "global"
        assert persisted.character_name == ""
        assert persisted.verbalized_form == "EE-jis"
    finally:
        session.close()


def test_unit_pronunciation_dictionary_character_scope_terms_can_be_created() -> None:
    session = get_session_factory()()
    try:
        project = Project(title="Character Pronunciation Dictionary")
        session.add(project)
        session.flush()

        entry = PronunciationDictionary(
            project_id=project.id,
            scope="character",
            character_name="Captain",
            term="Star",
            verbalized_form="Stahr",
            source="manual",
            confidence=0.9,
        )
        session.add(entry)
        session.commit()

        persisted = (
            session.query(PronunciationDictionary)
            .filter(
                PronunciationDictionary.project_id == project.id,
                PronunciationDictionary.scope == "character",
                PronunciationDictionary.character_name == "Captain",
                PronunciationDictionary.term == "Star",
            )
            .one()
        )
        assert persisted.character_name == "Captain"
        assert persisted.confidence == 0.9
    finally:
        session.close()


def test_unit_pronunciation_dictionary_rejects_duplicate_term_per_project_scope_character() -> None:
    session = get_session_factory()()
    try:
        project = Project(title="Pronunciation Dictionary Duplicate Guard")
        session.add(project)
        session.flush()

        session.add(
            PronunciationDictionary(
                project_id=project.id,
                scope="global",
                character_name="",
                term="Aegis",
                verbalized_form="EE-jis",
            )
        )
        session.flush()
        session.add(
            PronunciationDictionary(
                project_id=project.id,
                scope="global",
                character_name="",
                term="Aegis",
                verbalized_form="Eh-jiss",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_unit_pronunciation_dictionary_rejects_invalid_scope_value() -> None:
    session = get_session_factory()()
    try:
        project = Project(title="Pronunciation Dictionary Scope Guard")
        session.add(project)
        session.flush()

        session.add(
            PronunciationDictionary(
                project_id=project.id,
                scope="chapter",
                character_name="",
                term="Aegis",
                verbalized_form="EE-jis",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
