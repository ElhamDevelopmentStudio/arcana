from pathlib import Path

from sqlalchemy import create_engine, text

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        migration_dir = Path(__file__).parent / "migrations"
        for migration_file in sorted(migration_dir.glob("*.sql")):
            sql = migration_file.read_text(encoding="utf-8")
            statements = [part.strip() for part in sql.split(";") if part.strip()]
            for statement in statements:
                connection.execute(text(statement))
            print(f"Applied migration: {migration_file.name}")


if __name__ == "__main__":
    main()
