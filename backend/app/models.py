from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Float, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base
from app.services.encryption import EncryptedBinary, EncryptedText
from app.modes import DEFAULT_MODE


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_mode: Mapped[str] = mapped_column(String(50), nullable=False, default=DEFAULT_MODE)
    selected_modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    llm_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    configuration_snapshot_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    voice_config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    llm_provider_config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    default_narrator_voice: Mapped[str] = mapped_column(String(255), default="narrator_default", nullable=False)
    default_male_voice: Mapped[str] = mapped_column(String(255), default="male_default", nullable=False)
    default_female_voice: Mapped[str] = mapped_column(String(255), default="female_default", nullable=False)
    default_neutral_voice: Mapped[str] = mapped_column(String(255), default="neutral_default", nullable=False)
    default_unknown_voice: Mapped[str] = mapped_column(String(255), default="unknown_default", nullable=False)
    ingestion_log_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ingestion_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    character_map_finalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    chapters: Mapped[list["Chapter"]] = relationship("Chapter", back_populates="project")
    raw_corpus_blobs: Mapped[list["ProjectRawCorpusBlob"]] = relationship(
        "ProjectRawCorpusBlob",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    characters: Mapped[list["Character"]] = relationship("Character", back_populates="project")
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="project")
    run_configuration_snapshots: Mapped[list["RunConfigurationSnapshot"]] = relationship(
        "RunConfigurationSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    pronunciation_dictionary_entries: Mapped[list["PronunciationDictionary"]] = relationship(
        "PronunciationDictionary",
        back_populates="project",
    )
    voice_map_entries: Mapped[list["CharacterVoiceMap"]] = relationship(
        "CharacterVoiceMap",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    character_map_snapshots: Mapped[list["CharacterMapSnapshot"]] = relationship(
        "CharacterMapSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    voice_map_snapshots: Mapped[list["VoiceMapSnapshot"]] = relationship(
        "VoiceMapSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    pronunciation_dictionary_snapshots: Mapped[list["PronunciationDictionarySnapshot"]] = relationship(
        "PronunciationDictionarySnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    time_series_snapshots: Mapped[list["TimeSeriesSnapshot"]] = relationship(
        "TimeSeriesSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    comparison_workspace_runs: Mapped[list["ComparisonWorkspaceRun"]] = relationship(
        "ComparisonWorkspaceRun",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    access_controls: Mapped[list["ProjectAccess"]] = relationship(
        "ProjectAccess",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectAccess(Base):
    __tablename__ = "project_accesses"
    __table_args__ = (
        UniqueConstraint("project_id", "principal_type", "principal_id", name="uq_project_access_principal"),
        CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="ck_project_access_role"),
        CheckConstraint("principal_type IN ('user', 'service', 'system')", name="ck_project_access_principal_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(40), nullable=False, default="user")
    principal_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="access_controls")


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
    raw_text: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    original_text_snapshot: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    normalized_text: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    normalized_text_snapshot: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    original_to_normalized_offset_map: Mapped[list[dict[str, int | str]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    project: Mapped[Project] = relationship("Project", back_populates="chapters")


class ProjectRawCorpusBlob(Base):
    __tablename__ = "project_raw_corpus_blobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blob_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_corpus_blob: Mapped[bytes] = mapped_column(EncryptedBinary(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="raw_corpus_blobs")


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_character_name"),
        CheckConstraint(
            "gender IN ('male', 'female', 'neutral', 'unknown', 'custom')",
            name="ck_character_gender_allowed",
        ),
        CheckConstraint(
            "inferred_gender IN ('male', 'female', 'neutral', 'unknown', 'custom')",
            name="ck_character_inferred_gender_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    verbalized_form: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[str] = mapped_column(String(50), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="user_import")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    inferred_gender: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    inferred_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    inferred_source_trace: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    voice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voice_map: Mapped["CharacterVoiceMap | None"] = relationship(
        "CharacterVoiceMap",
        back_populates="character",
        uselist=False,
        cascade="all, delete-orphan",
    )

    project: Mapped[Project] = relationship("Project", back_populates="characters")


class CharacterVoiceMap(Base):
    __tablename__ = "character_voice_map"
    __table_args__ = (
        UniqueConstraint("project_id", "character_id", name="uq_project_character_voice_map"),
        UniqueConstraint("character_id", name="uq_character_voice_map_character_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="voice_map_entries")
    character: Mapped[Character] = relationship("Character", back_populates="voice_map")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    deterministic_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deterministic_model_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deterministic_randomization_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_model_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="runs")
    character_map_snapshot: Mapped["CharacterMapSnapshot | None"] = relationship(
        "CharacterMapSnapshot",
        back_populates="run",
        uselist=False,
    )
    run_configuration_snapshot: Mapped["RunConfigurationSnapshot | None"] = relationship(
        "RunConfigurationSnapshot",
        back_populates="run",
        uselist=False,
    )
    voice_map_snapshot: Mapped["VoiceMapSnapshot | None"] = relationship(
        "VoiceMapSnapshot",
        back_populates="run",
        uselist=False,
    )
    pronunciation_dictionary_snapshot: Mapped["PronunciationDictionarySnapshot | None"] = relationship(
        "PronunciationDictionarySnapshot",
        back_populates="run",
        uselist=False,
    )
    time_series_snapshot: Mapped["TimeSeriesSnapshot | None"] = relationship(
        "TimeSeriesSnapshot",
        back_populates="run",
        uselist=False,
    )
    comparison_workspace_runs: Mapped[list["ComparisonWorkspaceRun"]] = relationship(
        "ComparisonWorkspaceRun",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    changelog_entries: Mapped[list["RunChangelogEntry"]] = relationship(
        "RunChangelogEntry",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    normalized_corpus_blobs: Mapped[list["RunNormalizedCorpusBlob"]] = relationship(
        "RunNormalizedCorpusBlob",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class RunNormalizedCorpusBlob(Base):
    __tablename__ = "run_normalized_corpus_blobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    corpus_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_corpus_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped[Run] = relationship("Run", back_populates="normalized_corpus_blobs")


class CharacterMapSnapshot(Base):
    __tablename__ = "character_map_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_project_character_map_snapshot_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_json_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="character_map_snapshots")
    run: Mapped["Run | None"] = relationship("Run", back_populates="character_map_snapshot")


class RunConfigurationSnapshot(Base):
    __tablename__ = "run_configuration_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_project_run_configuration_snapshot_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_json_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="run_configuration_snapshots")
    run: Mapped["Run"] = relationship("Run", back_populates="run_configuration_snapshot")


class PronunciationDictionarySnapshot(Base):
    __tablename__ = "pronunciation_dictionary_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_project_pronunciation_dictionary_snapshot_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_json_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="pronunciation_dictionary_snapshots")
    run: Mapped["Run | None"] = relationship("Run", back_populates="pronunciation_dictionary_snapshot")


class VoiceMapSnapshot(Base):
    __tablename__ = "voice_map_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_project_voice_map_snapshot_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_json_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="voice_map_snapshots")
    run: Mapped["Run | None"] = relationship("Run", back_populates="voice_map_snapshot")


class TimeSeriesSnapshot(Base):
    __tablename__ = "time_series_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_project_time_series_snapshot_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_json_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="time_series_snapshots")
    run: Mapped["Run | None"] = relationship("Run", back_populates="time_series_snapshot")


class ComparisonWorkspace(Base):
    __tablename__ = "comparison_workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    runs: Mapped[list["ComparisonWorkspaceRun"]] = relationship(
        "ComparisonWorkspaceRun",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )


class ComparisonWorkspaceRun(Base):
    __tablename__ = "comparison_workspace_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "run_id",
            name="uq_workspace_run",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("comparison_workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    workspace: Mapped[ComparisonWorkspace] = relationship("ComparisonWorkspace", back_populates="runs")
    project: Mapped[Project] = relationship("Project", back_populates="comparison_workspace_runs")
    run: Mapped[Run] = relationship("Run", back_populates="comparison_workspace_runs")


class PronunciationDictionary(Base):
    __tablename__ = "pronunciation_dictionary"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "scope",
            "character_name",
            "term",
            name="uq_project_scope_character_term",
        ),
        CheckConstraint(
            "scope IN ('global', 'character', 'place', 'artifact', 'invented')",
            name="ck_pronunciation_dictionary_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    character_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    verbalized_form: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="user")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    project: Mapped[Project] = relationship("Project", back_populates="pronunciation_dictionary_entries")


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("run_id", "chapter_id", "segment_index", name="uq_run_chapter_segment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class SubSegmentTag(Base):
    __tablename__ = "sub_segment_tags"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "segment_id",
            "sub_segment_index",
            name="uq_run_segment_sub_segment_index",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id", ondelete="CASCADE"), nullable=False)
    sub_segment_id: Mapped[str] = mapped_column(String(80), nullable=False)
    sub_segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    shift_type: Mapped[str] = mapped_column(String(80), nullable=False)
    boundary_start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    boundary_end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    from_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    to_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    from_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    tags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_usage_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class RunChangelogEntry(Base):
    __tablename__ = "run_changelog_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    event_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped[Run] = relationship("Run", back_populates="changelog_entries")


class LLMCache(Base):
    __tablename__ = "llm_cache"
    __table_args__ = (
        UniqueConstraint(
            "input_text_hash",
            "task_type",
            "configuration_snapshot_id",
            "model_identifier",
            name="uq_llm_cache_input_text_hash_task_type_configuration_snapshot_model",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    input_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    configuration_snapshot_id: Mapped[str] = mapped_column(String(120), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
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
    last_rate_limit_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_rate_limit_status_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_rate_limit_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_call_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProviderApiKeyQuota(Base):
    __tablename__ = "provider_api_key_quota"
    __table_args__ = (UniqueConstraint("provider", "provider_api_key", "day_key", name="uq_provider_api_key_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    day_key: Mapped[str] = mapped_column(String(20), nullable=False)
    calls_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_calls_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_rate_limit_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_rate_limit_status_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_rate_limit_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_call_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProviderToggle(Base):
    __tablename__ = "provider_toggle"

    provider: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
