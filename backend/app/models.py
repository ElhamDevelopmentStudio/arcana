from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base
from app.modes import DEFAULT_MODE


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_mode: Mapped[str] = mapped_column(String(50), nullable=False, default=DEFAULT_MODE)
    selected_modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    configuration_snapshot_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    voice_config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ingestion_log_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ingestion_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    chapters: Mapped[list["Chapter"]] = relationship("Chapter", back_populates="project")
    characters: Mapped[list["Character"]] = relationship("Character", back_populates="project")
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="project")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("project_id", "chapter_index", name="uq_project_chapter_index"),
        UniqueConstraint("project_id", "chapter_internal_id", name="uq_project_chapter_internal_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_internal_id: Mapped[str] = mapped_column(String(80), nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="chapters")


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_project_character_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    verbalized_form: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[str] = mapped_column(String(50), nullable=False)
    voice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="characters")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="runs")


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("run_id", "chapter_id", "segment_index", name="uq_run_chapter_segment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class ProviderQuota(Base):
    __tablename__ = "provider_quota"
    __table_args__ = (UniqueConstraint("provider", "day_key", name="uq_provider_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    day_key: Mapped[str] = mapped_column(String(20), nullable=False)
    calls_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_calls_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
