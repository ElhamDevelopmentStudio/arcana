from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ProjectResponse(BaseModel):
    id: int
    title: str
    created_at: datetime


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
    max_segment_chars: int = Field(default=255, ge=80, le=255)
    llm_enabled: bool = False
    provider_name: str = "openrouter"
    max_calls_per_day: int = Field(default=25, ge=1, le=10000)

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
