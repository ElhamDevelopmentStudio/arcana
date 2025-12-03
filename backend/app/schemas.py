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
    selected_modes: list[str]
    configuration_snapshot_id: str | None
    character_map_finalized: bool
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
    selected_modes: list[str]
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


class CharacterSourceTrace(BaseModel):
    kind: str = Field(min_length=1)
    chapter_index: int = Field(ge=1)
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    excerpt: str = Field(min_length=1, max_length=400)
    weight: float = Field(ge=0.0, le=1.0)


class CharacterMapItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    verbalized_form: str = Field(min_length=1, max_length=255)
    gender: str = Field(min_length=1, max_length=50)
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None
    source: str = Field(default="manual", min_length=1, max_length=120)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_trace: list[CharacterSourceTrace] = Field(default_factory=list)

    @field_validator("gender")
    @classmethod
    def gender_normalized(cls, value: str) -> str:
        stripped = value.strip().lower()
        if not stripped:
            raise ValueError("gender must not be blank")
        return stripped

    @field_validator("aliases")
    @classmethod
    def aliases_trimmed(cls, values: list[str]) -> list[str]:
        cleaned = [alias.strip() for alias in values if str(alias).strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("source")
    @classmethod
    def source_defaulted(cls, value: str) -> str:
        stripped = value.strip()
        return stripped or "manual"


class CharacterMapResponse(BaseModel):
    project_id: int
    characters: list[CharacterMapItem]
    character_map_finalized: bool


class CharacterMapUpdateRequest(BaseModel):
    characters: list[CharacterMapItem]


class CharacterAliasLookupRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=255)

    @field_validator("alias")
    @classmethod
    def alias_normalized(cls, value: str) -> str:
        return value.strip()


class CharacterAliasLookupResponse(BaseModel):
    project_id: int
    alias: str = Field(min_length=1, max_length=255)
    canonical_name: str | None
    match_source: str = Field(default="none", min_length=1, max_length=20)


class CharacterAliasCollisionItem(BaseModel):
    alias: str = Field(min_length=1, max_length=255)
    canonical_names: list[str]


class CharacterAliasCollisionResponse(BaseModel):
    project_id: int
    collisions: list[CharacterAliasCollisionItem]


class CharacterMapFinalizeResponse(BaseModel):
    project_id: int
    character_map_finalized: bool


class CharacterScrapeRequest(BaseModel):
    source_url: str = Field(min_length=1, max_length=2048)
    acknowledge_source_risk: bool


class CharacterCandidatesMergeRequest(BaseModel):
    include_auto: bool = True
    source_url: str | None = Field(default=None, max_length=2048)
    acknowledge_source_risk: bool = False

    @field_validator("source_url")
    @classmethod
    def strip_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CanonicalNameMergeSuggestion(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=255)
    alias_name: str = Field(min_length=1, max_length=255)
    score: float = Field(ge=0.0, le=1.0)
    candidate_source: str = Field(min_length=1, max_length=120)
    canonical_source: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=200)


class CharacterExtractionResponse(BaseModel):
    project_id: int
    status: str
    candidate_count: int
    candidates: list[CharacterMapItem]
    proposed_characters: list[CharacterMapItem] = Field(default_factory=list)
    canonical_merge_suggestions: list[CanonicalNameMergeSuggestion] = Field(default_factory=list)


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
    allow_unfinalized_character_map: bool = False

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


class CharacterMentionsByChapterItem(BaseModel):
    chapter_index: int
    mention_counts: dict[str, int]


class CharacterOccurrenceAnalyticsResponse(BaseModel):
    project_id: int
    run_id: int
    character_mentions_by_chapter: list[CharacterMentionsByChapterItem]
    character_first_appearance_chapter_index: dict[str, int | None]
    character_last_appearance_chapter_index: dict[str, int | None]
    character_mentions_per_1000_words: dict[str, float]
    character_dialogue_line_counts: dict[str, int]
