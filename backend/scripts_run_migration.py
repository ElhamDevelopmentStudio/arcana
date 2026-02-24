from pathlib import Path

from sqlalchemy import create_engine, text

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    migration_file = Path(__file__).parent / "migrations" / "001_initial.sql"
    sql = migration_file.read_text(encoding="utf-8")

    statements = [part.strip() for part in sql.split(";\n\n") if part.strip()]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    print("Applied migration: 001_initial.sql")


if __name__ == "__main__":
    main()
