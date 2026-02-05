from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def reset_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _apply_schema_compatibility_updates(engine)


def _apply_schema_compatibility_updates(engine) -> None:
    inspector = inspect(engine)
    if "projects" not in set(inspector.get_table_names()):
        return

    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "lifecycle_state" in project_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE projects ADD COLUMN lifecycle_state VARCHAR(40) NOT NULL DEFAULT 'draft'"
            )
        )


def get_session() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
