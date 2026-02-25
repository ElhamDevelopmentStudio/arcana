from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modes import DEFAULT_MODE, is_valid_mode


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ProjectResponse(BaseModel):
    id: int
    title: str
    selected_mode: str
    ingestion_timestamp: datetime | None
    created_at: datetime


def _normalize_mode_or_raise(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        raise ValueError("mode must not be blank")
    if not is_valid_mode(stripped):
        raise ValueError("mode must be one of: audiobook, academic, author, custom")
    return stripped


class ProjectModeSwitchRequest(BaseModel):
    mode: str = Field(min_length=1)

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, value: str) -> str:
        return _normalize_mode_or_raise(value)


class ProjectModeSwitchResponse(BaseModel):
    project_id: int
    previous_mode: str
    selected_mode: str
    chapter_count: int
    reused_ingested_corpus: bool
    stale_runs_marked: int


class ModeDefaultProfileResponse(BaseModel):
    max_segment_chars: int = Field(ge=80, le=255)
    llm_enabled: bool
    provider_name: str = Field(min_length=1)
    max_calls_per_day: int = Field(ge=1, le=10000)
    profile_intent: str = Field(min_length=1)


class ModeCatalogResponse(BaseModel):
    modes: list[str]
    default_mode: str
    persisted_in: list[str]
    mode_profiles: dict[str, ModeDefaultProfileResponse]


class IngestResponse(BaseModel):
    project_id: int
    chapter_count: int


class CharacterImportResponse(BaseModel):
    project_id: int
    imported_count: int


class VoiceConfigRequest(BaseModel):
    narrator_voice: str = Field(min_length=1)
    male_default_voice: str = Field(min_length=1)
    female_default_voice: str = Field(min_length=1)


class VoiceConfigResponse(BaseModel):
    project_id: int
    voice_config: dict[str, str]


class RunCreateRequest(BaseModel):
    mode: str = Field(default=DEFAULT_MODE)
    max_segment_chars: int = Field(default=255, ge=80, le=255)
    llm_enabled: bool = False
    provider_name: str = "openrouter"
    max_calls_per_day: int = Field(default=25, ge=1, le=10000)

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, value: str) -> str:
        return _normalize_mode_or_raise(value)

    @field_validator("provider_name")
    @classmethod
    def provider_name_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("provider_name must not be blank")
        return stripped.lower()


class RunResponse(BaseModel):
    run_id: int
    project_id: int
    status: str
    segment_count: int


class RunDetailResponse(BaseModel):
    run_id: int
    project_id: int
    status: str
    config: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None
    segment_count: int
    llm_calls: list[dict[str, Any]]
