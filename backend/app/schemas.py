from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
from app.services.tagging import (
    TAG_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
    TAG_LOW_CONFIDENCE_THRESHOLD,
    TAG_UNSTABLE_RAPID_EMOTION_SHIFT_DENSITY,
    TAG_UNSTABLE_RAPID_EMOTION_SHIFT_THRESHOLD,
)

from app.modes import DEFAULT_MODE, is_valid_mode
from app.services.run_status import RunStatus


ALLOWED_PROJECT_ACCESS_ROLES = frozenset({"owner", "editor", "viewer"})
ALLOWED_PROJECT_ACCESS_PRINCIPAL_TYPES = frozenset({"user", "service", "system"})
ALLOWED_RUN_EXPORT_FORMATS = frozenset(
    {"json", "csv", "time_series_json", "graph_json"}
)


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    do_not_store_source_text: bool = False


class ProjectResponse(BaseModel):
    id: int
    title: str
    selected_mode: str
    selected_modes: list[str]
    llm_enabled: bool
    do_not_store_source_text: bool = False
    configuration_snapshot_id: str | None
    character_map_finalized: bool
    ingestion_timestamp: datetime | None
    created_at: datetime


ALLOWED_INITIAL_INGESTION_SOURCES = frozenset({"txt", "markdown", "epub", "chapters-dir"})


class ProjectIngestionSourceAttachRequest(BaseModel):
    source: str = Field(min_length=1, max_length=40)
    source_filename: str | None = Field(default=None, max_length=255)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in ALLOWED_INITIAL_INGESTION_SOURCES:
            raise ValueError("source must be one of: txt, markdown, epub, chapters-dir")
        return normalized

    @field_validator("source_filename")
    @classmethod
    def normalize_source_filename(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized


class ProjectIngestionSourceAttachResponse(BaseModel):
    project_id: int
    source: str
    source_filename: str | None = None
    attached_at: datetime


class ProjectMetadataUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_tag in value:
            trimmed = str(raw_tag).strip()
            if not trimmed:
                continue
            canonical = trimmed.lower()
            if canonical in seen:
                continue
            seen.add(canonical)
            normalized.append(trimmed)
        return normalized

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "ProjectMetadataUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("at least one metadata field must be provided")
        return self


class ProjectMetadataUpdateResponse(BaseModel):
    project_id: int
    title: str
    description: str | None
    tags: list[str]
    updated_at: datetime


class ProjectAccessGrantRequest(BaseModel):
    principal_id: str = Field(min_length=1, max_length=255)
    principal_type: str = Field(default="user", min_length=1, max_length=40)
    role: str = Field(default="viewer", min_length=1, max_length=40)

    @field_validator("principal_type")
    @classmethod
    def normalize_principal_type(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in ALLOWED_PROJECT_ACCESS_PRINCIPAL_TYPES:
            raise ValueError("principal_type must be one of: user, service, system")
        return normalized

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in ALLOWED_PROJECT_ACCESS_ROLES:
            raise ValueError("role must be one of: owner, editor, viewer")
        return normalized


class ProjectAccessGrantResponse(BaseModel):
    id: int
    project_id: int
    principal_type: str
    principal_id: str
    role: str
    created_at: datetime


class ProjectAccessListResponse(BaseModel):
    project_id: int
    grants: list[ProjectAccessGrantResponse]


class ProjectLLMSettingsRequest(BaseModel):
    llm_enabled: bool
    provider_config: dict[str, dict[str, object] | object] | None = None

    @field_validator("provider_config", mode="before")
    @classmethod
    def normalize_provider_config(cls, value: dict[str, object] | None) -> dict[str, dict[str, object]] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("provider_config must be an object map")

        normalized: dict[str, dict[str, object]] = {}
        for provider_name, provider_config in value.items():
            normalized_provider_name = str(provider_name).strip().lower()
            if not normalized_provider_name:
                continue
            if provider_config is None:
                continue
            if not isinstance(provider_config, dict):
                raise ValueError("provider_config values must be provider configuration objects")

            normalized_config: dict[str, object] = {}
            base_url = provider_config.get("base_url")
            if isinstance(base_url, str):
                normalized_base_url = base_url.strip()
                if normalized_base_url:
                    normalized_config["base_url"] = normalized_base_url

            model = provider_config.get("model")
            if isinstance(model, str):
                normalized_model = model.strip()
                if normalized_model:
                    normalized_config["model"] = normalized_model

            api_key = provider_config.get("api_key")
            if isinstance(api_key, str):
                normalized_api_key = api_key.strip()
                if normalized_api_key:
                    normalized_config["api_key"] = normalized_api_key

            api_keys = provider_config.get("api_keys")
            if api_keys is not None:
                if isinstance(api_keys, str):
                    parsed_api_keys = [entry.strip() for entry in api_keys.split(",")]
                elif isinstance(api_keys, (list, tuple, set)):
                    parsed_api_keys = [str(item).strip() for item in api_keys]
                else:
                    parsed_api_keys = [str(api_keys).strip()]

                normalized_api_keys = [item for item in parsed_api_keys if item]
                if normalized_api_keys:
                    normalized_config["api_keys"] = normalized_api_keys

            if normalized_config:
                normalized[normalized_provider_name] = normalized_config

        return normalized if normalized else None


class ProjectLLMSettingsResponse(BaseModel):
    project_id: int
    llm_enabled: bool
    provider_config: dict[str, dict[str, object]] = Field(default_factory=dict)


class LLMProviderStatus(BaseModel):
    provider: str = Field(min_length=1)
    enabled: bool


class LLMProviderStatusUpdateRequest(BaseModel):
    enabled: bool


class LLMProvidersResponse(BaseModel):
    providers: list[LLMProviderStatus]


ALLOWED_GENDER_VALUES = frozenset({"male", "female", "neutral", "unknown", "custom"})
INTERNAL_THOUGHT_VOICE_POLICIES = frozenset({"character", "narrator", "thought_voice"})


def _normalize_mode_or_raise(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        raise ValueError("mode must not be blank")
    if not is_valid_mode(stripped):
        raise ValueError("mode must be one of: audiobook, academic, author, custom")
    return stripped


def _normalize_gender_or_raise(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        raise ValueError("gender must not be blank")
    if stripped not in ALLOWED_GENDER_VALUES:
        raise ValueError("gender must be one of: male, female, neutral, unknown, custom")
    return stripped


def _normalize_internal_thought_voice_policy_or_raise(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        raise ValueError("internal_thought_voice_policy must not be blank")
    if stripped not in INTERNAL_THOUGHT_VOICE_POLICIES:
        raise ValueError(
            "internal_thought_voice_policy must be one of: character, narrator, thought_voice"
        )
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
    export_formats: list[str]
    export_chunk_size: int = Field(ge=1, le=10000)
    llm_enabled: bool
    provider_name: str = Field(min_length=1)
    max_calls_per_day: int = Field(ge=1, le=10000)
    llm_confidence_threshold: float = Field(ge=0.0, le=1.0)
    speaker_confidence_threshold: float = Field(ge=0.0, le=1.0)
    high_ambiguity_dialogue_flag_threshold: int = Field(ge=1, le=10)
    unstable_emotion_shift_transition_threshold: int = Field(ge=1, le=20)
    unstable_emotion_shift_density_threshold: float = Field(ge=0.0, le=1.0)
    deep_semantic_refinement: bool
    deterministic_mode: bool
    contradiction_review_required: bool
    web_scraping_enabled: bool
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
    voice_id: str | None = Field(default=None)
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None
    source: str = Field(default="manual", min_length=1, max_length=120)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    inferred_gender: str = Field(default="unknown", min_length=1, max_length=50)
    inferred_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    inferred_source_trace: list[CharacterSourceTrace] = Field(default_factory=list)
    source_trace: list[CharacterSourceTrace] = Field(default_factory=list)

    @field_validator("gender")
    @classmethod
    def gender_normalized(cls, value: str) -> str:
        return _normalize_gender_or_raise(value)

    @field_validator("voice_id")
    @classmethod
    def voice_id_normalized(cls, value: str | None) -> str | None:
        if value is None:
            return None

        trimmed = str(value).strip()
        if not trimmed:
            return None
        if len(trimmed) > 255:
            raise ValueError("voice_id must be 255 characters or fewer")
        return trimmed

    @field_validator("aliases")
    @classmethod
    def aliases_trimmed(cls, values: list[str]) -> list[str]:
        cleaned = [alias.strip() for alias in values if str(alias).strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("inferred_gender")
    @classmethod
    def inferred_gender_normalized(cls, value: str) -> str:
        return _normalize_gender_or_raise(value)

    @field_validator("source")
    @classmethod
    def source_defaulted(cls, value: str) -> str:
        stripped = value.strip()
        return stripped or "manual"


class CharacterMapResponse(BaseModel):
    project_id: int
    characters: list[CharacterMapItem]
    character_map_finalized: bool


class CharacterGenderComparisonItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    manual_gender: str = Field(min_length=1, max_length=50)
    inferred_gender: str = Field(min_length=1, max_length=50)
    manual_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    inferred_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    comparison: str = Field(min_length=1, max_length=80)
    contradiction_severity: float = Field(default=0.0, ge=0.0, le=1.0)
    is_contradiction: bool
    requires_review: bool

    @field_validator("manual_gender")
    @classmethod
    def manual_gender_normalized(cls, value: str) -> str:
        return _normalize_gender_or_raise(value)

    @field_validator("inferred_gender")
    @classmethod
    def inferred_gender_normalized(cls, value: str) -> str:
        return _normalize_gender_or_raise(value)


class CharacterGenderWarningItem(BaseModel):
    type: str = Field(min_length=1)
    level: str = Field(min_length=1)
    source: str = Field(min_length=1)
    character_name: str = Field(min_length=1)
    manual_gender: str = Field(min_length=1, max_length=50)
    inferred_gender: str = Field(min_length=1, max_length=50)
    manual_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    inferred_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    contradiction_severity: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_review: bool
    message: str = Field(min_length=1)

    @field_validator("manual_gender")
    @classmethod
    def manual_gender_normalized(cls, value: str) -> str:
        return _normalize_gender_or_raise(value)

    @field_validator("inferred_gender")
    @classmethod
    def inferred_gender_normalized(cls, value: str) -> str:
        return _normalize_gender_or_raise(value)


class CharacterGenderComparisonResponse(BaseModel):
    project_id: int
    comparison_count: int
    contradiction_count: int
    comparisons: list[CharacterGenderComparisonItem]
    warnings: list[CharacterGenderWarningItem] = Field(default_factory=list)


class CharacterMapUpdateRequest(BaseModel):
    characters: list[CharacterMapItem]


class PronunciationDictionaryItem(BaseModel):
    term: str = Field(min_length=1, max_length=255)
    verbalized_form: str = Field(min_length=1, max_length=255)
    source: str = Field(default="user", min_length=1, max_length=120)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("term")
    @classmethod
    def normalize_term(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("term must not be blank")
        return stripped

    @field_validator("verbalized_form")
    @classmethod
    def normalize_verbalized_form(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("verbalized_form must not be blank")
        return stripped

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        stripped = value.strip()
        return stripped or "user"


class PronunciationDictionaryUpdateRequest(BaseModel):
    entries: list[PronunciationDictionaryItem]


class PronunciationDictionaryResponse(BaseModel):
    project_id: int
    scope: str
    entries: list[PronunciationDictionaryItem]


class PronunciationDictionaryPreviewItem(BaseModel):
    term: str
    verbalized_form: str
    count: int = Field(ge=1)
    scope: str


class PronunciationDictionaryPreviewWarning(BaseModel):
    type: str = Field(min_length=1, max_length=120)
    term: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=500)
    scopes: list[str]
    competing_verbalized_forms: list[str]


class PronunciationDictionaryPreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    character_name: str | None = None
    include_global_scope: bool = True
    include_character_scope: bool = True
    include_place_scope: bool = False
    include_artifact_scope: bool = False
    include_invented_scope: bool = False
    match_whole_words: bool = True
    case_sensitive: bool = True
    alias_aware: bool = False

    @field_validator("character_name")
    @classmethod
    def normalize_character_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PronunciationDictionaryPreviewResponse(BaseModel):
    project_id: int
    before: str
    after: str
    character_name: str | None
    replacements: list[PronunciationDictionaryPreviewItem]
    included_scopes: list[str]
    warnings: list[PronunciationDictionaryPreviewWarning] = Field(default_factory=list)


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


class CharacterWarning(BaseModel):
    type: str = Field(min_length=1, max_length=120)
    level: str = Field(default="warning", min_length=1, max_length=20)
    source: str = Field(default="character", min_length=1, max_length=120)
    alias: str = Field(min_length=1, max_length=255)
    canonical_names: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1, max_length=400)
    candidate_name: str | None = Field(default=None, min_length=0, max_length=255)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class CharacterExtractionResponse(BaseModel):
    project_id: int
    status: str
    candidate_count: int
    candidates: list[CharacterMapItem]
    proposed_characters: list[CharacterMapItem] = Field(default_factory=list)
    canonical_merge_suggestions: list[CanonicalNameMergeSuggestion] = Field(default_factory=list)
    warnings: list[CharacterWarning] = Field(default_factory=list)


class VoiceConfigRequest(BaseModel):
    narrator_voice: str = Field(min_length=1)
    male_default_voice: str = Field(min_length=1)
    female_default_voice: str = Field(min_length=1)
    neutral_default_voice: str = Field(default="neutral_default", min_length=1)
    unknown_default_voice: str = Field(default="unknown_default", min_length=1)
    internal_thought_voice_policy: str = "character"
    internal_thought_voice: str | None = None

    @field_validator("internal_thought_voice_policy")
    @classmethod
    def internal_thought_voice_policy_must_be_valid(cls, value: str) -> str:
        return _normalize_internal_thought_voice_policy_or_raise(value)

    @field_validator("internal_thought_voice")
    @classmethod
    def internal_thought_voice_must_be_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > 255:
            raise ValueError("internal_thought_voice must be 255 characters or fewer")
        return trimmed


class VoiceConfigResponse(BaseModel):
    project_id: int
    voice_config: dict[str, str]


class RunCreateRequest(BaseModel):
    mode: str = Field(default=DEFAULT_MODE)
    pipeline_chunk_max_chars: int | None = Field(default=None, ge=1024, le=2_000_000)
    max_segment_chars: int = Field(
        default=255,
        ge=80,
        le=255,
        validation_alias=AliasChoices("max_segment_chars", "segmentation_target_length"),
    )
    llm_enabled: bool = False
    provider_name: str = "openrouter"
    export_formats: list[str] | None = None
    export_chunk_size: int | None = Field(default=None, ge=1, le=10000)
    deep_semantic_refinement: bool = False
    deterministic_mode: bool = False
    contradiction_review_required: bool = True
    max_calls_per_day: int = Field(default=25, ge=1, le=10000)
    llm_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    speaker_confidence_threshold: float = Field(
        default=TAG_LOW_CONFIDENCE_THRESHOLD,
        ge=0.0,
        le=1.0,
    )
    high_ambiguity_dialogue_flag_threshold: int = Field(
        default=TAG_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
        ge=1,
        le=20,
    )
    unstable_emotion_shift_transition_threshold: int = Field(
        default=TAG_UNSTABLE_RAPID_EMOTION_SHIFT_THRESHOLD,
        ge=1,
        le=20,
    )
    unstable_emotion_shift_density_threshold: float = Field(
        default=TAG_UNSTABLE_RAPID_EMOTION_SHIFT_DENSITY,
        ge=0.0,
        le=1.0,
    )
    deterministic_model_identifier: str | None = None
    web_scraping_enabled: bool = False
    deterministic_seed: int | None = Field(default=None, ge=0)
    randomization_config: dict[str, object] | None = None
    provider_api_keys: dict[str, list[str]] | None = None
    emotion_taxonomy: str = "basic"
    allow_unfinalized_character_map: bool = False
    internal_thought_voice_policy: str = "character"
    internal_thought_voice: str | None = None
    incremental_recompute: bool = False
    idempotency_key: str | None = None

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

    @field_validator("export_formats", mode="before")
    @classmethod
    def export_formats_must_be_normalized(
        cls,
        value: list[str] | tuple[str, ...] | set[str] | object | None,
    ) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("export_formats must be a list of strings")

        normalized: list[str] = []
        seen: set[str] = set()
        for raw_format in value:
            if not isinstance(raw_format, str):
                raise ValueError("export_formats values must be strings")
            normalized_format = raw_format.strip().lower()
            if not normalized_format:
                continue
            if normalized_format not in ALLOWED_RUN_EXPORT_FORMATS:
                raise ValueError("export_formats must be one of: json, csv, time_series_json, graph_json")
            if normalized_format not in seen:
                normalized.append(normalized_format)
                seen.add(normalized_format)

        if not normalized:
            raise ValueError("export_formats must contain at least one value")

        return normalized

    @field_validator("internal_thought_voice_policy")
    @classmethod
    def internal_thought_voice_policy_must_be_valid(cls, value: str) -> str:
        return _normalize_internal_thought_voice_policy_or_raise(value)

    @field_validator("emotion_taxonomy")
    @classmethod
    def emotion_taxonomy_must_be_valid(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if not normalized:
            return "basic"
        if normalized not in {"basic", "expanded"}:
            raise ValueError("emotion_taxonomy must be one of: basic, expanded")
        return normalized

    @field_validator("internal_thought_voice")
    @classmethod
    def internal_thought_voice_must_be_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > 255:
            raise ValueError("internal_thought_voice must be 255 characters or fewer")
        return trimmed

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_key_must_be_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > 255:
            raise ValueError("idempotency_key must be 255 characters or fewer")
        return trimmed

    @field_validator("deterministic_model_identifier")
    @classmethod
    def deterministic_model_identifier_must_be_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > 255:
            raise ValueError("deterministic_model_identifier must be 255 characters or fewer")
        return trimmed

    @field_validator("deterministic_seed")
    @classmethod
    def deterministic_seed_must_be_non_negative(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError("deterministic_seed must be 0 or greater")
        return value

    @field_validator("randomization_config")
    @classmethod
    def randomization_config_must_be_mapping(cls, value: dict[str, object] | None) -> dict[str, object] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("randomization_config must be an object mapping")
        return value

    @field_validator("provider_api_keys", mode="before")
    @classmethod
    def normalize_provider_api_keys(cls, value: dict[str, object] | None) -> dict[str, list[str]] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("provider_api_keys must be an object map")

        normalized: dict[str, list[str]] = {}
        for provider, api_keys in value.items():
            provider_name = str(provider).strip().lower()
            if not provider_name:
                continue

            if api_keys is None:
                continue
            if isinstance(api_keys, str):
                keys = [entry.strip() for entry in api_keys.split(",")]
            elif isinstance(api_keys, (list, tuple, set)):
                keys = []
                for entry in api_keys:
                    if entry is None:
                        continue
                    keys.append(str(entry).strip())
            else:
                keys = [str(api_keys).strip()]

            cleaned = [key for key in keys if key]
            if not cleaned:
                continue

            normalized[provider_name] = cleaned

        return normalized if normalized else None


class RunResponse(BaseModel):
    run_id: int
    project_id: int
    status: RunStatus
    segment_count: int


class RunLLMCallLog(BaseModel):
    id: int
    provider: str
    task_type: str
    success: bool
    request_count: int
    token_usage_estimate: int | None
    model_identifier: str | None
    called_at: str | None
    detail: str | None
    created_at: datetime
    is_cache_hit: bool


class RunChangelogEntry(BaseModel):
    id: int
    event_type: str
    event_message: str | None = None
    event_metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class LLMCacheMetrics(BaseModel):
    hits: int = Field(ge=0)
    misses: int = Field(ge=0)


class RunDetailResponse(BaseModel):
    run_id: int
    project_id: int
    status: RunStatus
    llm_provider_name: str | None = None
    llm_model_identifier: str | None = None
    llm_model_version: str | None = None
    config: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None
    segment_count: int
    llm_cache_metrics: dict[str, LLMCacheMetrics] = Field(default_factory=dict)
    llm_calls: list[RunLLMCallLog]
    changelog_entries: list[RunChangelogEntry] = Field(default_factory=list)


class RunConfigFieldDiff(BaseModel):
    field: str = Field(min_length=1)
    base_value: Any | None = None
    target_value: Any | None = None


class RunConfigDiffResponse(BaseModel):
    project_id: int
    base_run_id: int
    target_run_id: int
    base_config_schema_version: str = Field(default="1.0.0", min_length=1)
    target_config_schema_version: str = Field(default="1.0.0", min_length=1)
    is_identical: bool
    changed_fields: list[RunConfigFieldDiff] = Field(default_factory=list)
    base_only_fields: list[str] = Field(default_factory=list)
    target_only_fields: list[str] = Field(default_factory=list)


class RunConfigPresetResponse(BaseModel):
    project_id: int
    run_id: int
    preset_schema_version: str = Field(default="1.0.0", min_length=1)
    generated_at: str = Field(min_length=1)
    run_config: dict[str, Any] = Field(default_factory=dict)


class NarrativeHealthChapterRange(BaseModel):
    start_chapter: int = Field(ge=1)
    end_chapter: int = Field(ge=1)
    start_segment: int | None = Field(default=None, ge=1)
    end_segment: int | None = Field(default=None, ge=1)


class NarrativeHealthActionableFinding(BaseModel):
    requirement_id: str = Field(pattern=r"^ADR-\d{3}$", min_length=1, max_length=20)
    requirement_name: str = Field(min_length=1, max_length=255)
    location: NarrativeHealthChapterRange
    trigger_metric: str = Field(min_length=1, max_length=255)
    severity: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("evidence", "evidence_trace"),
        serialization_alias="evidence",
    )


class NarrativeChapterTypeClassification(BaseModel):
    chapter_id: int = Field(ge=1)
    chapter_type: Literal["setup", "build-up", "confrontation", "resolution", "transitional"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)


class NarrativeHealthRequirementReport(BaseModel):
    requirement_id: str = Field(pattern=r"^ADR-\d{3}$", min_length=1, max_length=20)
    status: Literal["implemented", "partial", "not_implemented", "blocked"]
    finding_count: int = Field(ge=0)
    requirement_name: str = Field(min_length=1, max_length=255)
    findings: list[NarrativeHealthActionableFinding] = Field(default_factory=list)


class NarrativeHealthReport(BaseModel):
    schema_version: str = Field(default="1.0.0", min_length=1)
    output_schema: str = Field(default="author_narrative_health_json", min_length=1)
    generated_at: str
    generated_by: str = Field(default="build_run_export", min_length=1)
    project_reference: dict[str, Any]
    run_reference: dict[str, Any]
    requirements: list[NarrativeHealthRequirementReport]
    chapter_type_classification: list[NarrativeChapterTypeClassification] = Field(
        default_factory=list
    )
    findings: list[NarrativeHealthActionableFinding] = Field(default_factory=list)


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


class CharacterCooccurrenceGraphNode(BaseModel):
    character_key: str = Field(min_length=1)
    character_label: str = Field(min_length=1)
    speaker_id: int | None = None
    segment_count: int = Field(ge=0)
    chapter_ids: list[int] = Field(default_factory=list)
    chapter_count: int = Field(ge=0)
    adjacency_weight: int = Field(ge=0)


class CharacterCooccurrenceGraphEdge(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    co_occurrence_count: int = Field(ge=0)
    weight: int = Field(ge=0)
    chapter_ids: list[int] = Field(default_factory=list)
    chapter_count: int = Field(ge=0)


class CharacterCooccurrenceGraphMetadata(BaseModel):
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    scope: str = Field(default="adjacent_speaker_transitions_within_chapter")
    undirected: bool = True
    generated_by: str = Field(default="export_academic_graph")


class CharacterCooccurrenceGraphData(BaseModel):
    nodes: list[CharacterCooccurrenceGraphNode] = Field(default_factory=list)
    edges: list[CharacterCooccurrenceGraphEdge] = Field(default_factory=list)
    metadata: CharacterCooccurrenceGraphMetadata


class CharacterCooccurrenceCentralityMetadata(BaseModel):
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    centrality_metrics: list[str] = Field(default_factory=list)
    distance_transform: str | None = None
    generated_by: str = Field(default="export_academic_centrality")


class CharacterCooccurrenceCentralityRow(BaseModel):
    character_key: str = Field(min_length=1)
    character_label: str = Field(min_length=1)
    speaker_id: int | None = None
    rank: int = Field(ge=1)
    degree: int = Field(ge=0)
    weighted_degree: float = Field(ge=0.0)
    degree_centrality: float = Field(ge=0.0, le=1.0)
    weighted_degree_centrality: float = Field(ge=0.0, le=1.0)
    closeness_centrality: float = Field(ge=0.0, le=1.0)
    betweenness_centrality: float = Field(ge=0.0, le=1.0)


class CharacterCooccurrenceCentralityPayload(BaseModel):
    metrics_table: list[CharacterCooccurrenceCentralityRow] = Field(default_factory=list)
    metadata: CharacterCooccurrenceCentralityMetadata


class CharacterCooccurrenceGraphResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="graph_json")
    output_format: str = Field(default="graph_json")
    output_id: str = Field(default="AO-004")
    output_name: str = Field(default="character_cooccurrence_graph")
    project_id: int
    run_id: int
    run_status: RunStatus
    generated_at: str
    generated_by: str = Field(default="build_run_export_graph_json")
    graph: CharacterCooccurrenceGraphData
    character_cooccurrence_centrality: CharacterCooccurrenceCentralityPayload
    manifest_snapshot: dict[str, Any] = Field(default_factory=dict)


class AudiobookPrepDashboardReadiness(BaseModel):
    is_ready: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    warning_reasons: list[str] = Field(default_factory=list)


class AudiobookPrepDashboardResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="audiobook_prep_dashboard_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="AB-001")
    output_name: str = Field(default="audiobook_prep_dashboard")
    project_id: int
    run_id: int
    run_status: RunStatus
    generated_at: str
    generated_by: str = Field(default="build_audiobook_prep_dashboard")
    unresolved_speaker_count: int = Field(ge=0)
    unresolved_voice_mapping_count: int = Field(ge=0)
    low_confidence_region_count: int = Field(ge=0)
    export_readiness: AudiobookPrepDashboardReadiness


class PipelineStageDurationItem(BaseModel):
    stage_name: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    memory_bytes_start: int | None = Field(default=None, ge=0)
    memory_bytes_end: int | None = Field(default=None, ge=0)
    memory_bytes_delta: int | None = None
    share_of_total: float = Field(ge=0.0, le=1.0)


class PipelineStageDurationsDashboardResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="pipeline_stage_durations_dashboard_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="OBS-001")
    output_name: str = Field(default="pipeline_stage_durations_dashboard")
    project_id: int
    run_id: int
    run_status: RunStatus
    generated_at: str
    generated_by: str = Field(default="build_pipeline_stage_durations_dashboard")
    total_duration_ms: int = Field(ge=0)
    stage_count: int = Field(ge=0)
    slowest_stage_name: str | None = None
    slowest_stage_duration_ms: int | None = Field(default=None, ge=0)
    stages: list[PipelineStageDurationItem] = Field(default_factory=list)


ProjectLifecycleState = Literal["draft", "ingested", "configured", "running", "completed", "failed", "archived"]
ProjectControlPanelNextRequiredAction = Literal[
    "ingest",
    "select_mode",
    "configure",
    "run",
    "rerun",
    "export",
    "review_failure",
    "archived",
    "none",
]
ProjectAllowedAction = Literal[
    "ingest",
    "select_mode",
    "configure",
    "run",
    "rerun",
    "export",
    "archive",
    "restore",
]
ProjectActionRunStatus = Literal["queued", "running", "completed", "failed", "cancelled", "interrupted"]
ProjectSetupStepId = Literal["ingestion", "mode_selection", "initial_run", "character_mapping", "voice_mapping"]
ProjectActivityTimelineEventType = Literal[
    "ingest",
    "mode_change",
    "run_start",
    "run_complete",
    "export",
    "manual_edit",
    "rerun",
]


class ProjectControlPanelStateCount(BaseModel):
    lifecycle_state: ProjectLifecycleState
    project_count: int = Field(ge=0)


class ProjectControlPanelRecentFailureItem(BaseModel):
    project_id: int = Field(ge=1)
    project_title: str = Field(min_length=1, max_length=255)
    run_id: int | None = Field(default=None, ge=1)
    failed_at: str = Field(min_length=1)
    error_code: str | None = Field(default=None, min_length=1, max_length=120)
    error_message: str | None = Field(default=None, min_length=1, max_length=1000)


class ProjectControlPanelSummaryResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_control_panel_summary_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-001")
    output_name: str = Field(default="project_control_panel_summary")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_control_panel_summary", min_length=1)
    total_projects: int = Field(ge=0)
    project_counts_by_state: list[ProjectControlPanelStateCount] = Field(default_factory=list)
    active_run_count: int = Field(ge=0)
    blocked_export_project_count: int = Field(ge=0)
    blocked_export_run_count: int = Field(ge=0)
    recent_failure_count: int = Field(ge=0)
    recent_failures: list[ProjectControlPanelRecentFailureItem] = Field(default_factory=list)


class ProjectControlPanelProjectListItem(BaseModel):
    project_id: int = Field(ge=1)
    status: ProjectLifecycleState
    selected_mode: str = Field(min_length=1, max_length=50)
    last_run_status: RunStatus | None = None
    updated_at: str = Field(min_length=1)
    next_required_action: ProjectControlPanelNextRequiredAction


class ProjectControlPanelProjectListResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_control_panel_project_list_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-002")
    output_name: str = Field(default="project_control_panel_project_list")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_control_panel_project_list", min_length=1)
    total_items: int = Field(ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    has_next_page: bool = False
    items: list[ProjectControlPanelProjectListItem] = Field(default_factory=list)


class ProjectAllowedActionsResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_allowed_actions_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-003")
    output_name: str = Field(default="project_allowed_actions")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_allowed_actions", min_length=1)
    project_id: int = Field(ge=1)
    lifecycle_state: ProjectLifecycleState
    last_run_status: ProjectActionRunStatus | None = None
    next_required_action: ProjectControlPanelNextRequiredAction
    allowed_actions: list[ProjectAllowedAction] = Field(default_factory=list)


class ProjectSetupStepStatus(BaseModel):
    step_id: ProjectSetupStepId
    label: str = Field(min_length=1, max_length=80)
    ready: bool
    required: bool = True


class ProjectSetupStatusResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_setup_status_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-007")
    output_name: str = Field(default="project_setup_status")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_setup_status", min_length=1)
    project_id: int = Field(ge=1)
    lifecycle_state: ProjectLifecycleState
    next_required_action: ProjectControlPanelNextRequiredAction
    is_complete: bool
    steps: list[ProjectSetupStepStatus] = Field(default_factory=list)


class ProjectWorkspaceSummaryResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_workspace_summary_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-008")
    output_name: str = Field(default="project_workspace_summary")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_workspace_summary", min_length=1)
    project_id: int = Field(ge=1)
    lifecycle_state: ProjectLifecycleState
    last_run_status: ProjectActionRunStatus | None = None
    next_required_action: ProjectControlPanelNextRequiredAction
    is_setup_complete: bool
    chapters_count: int = Field(ge=0)
    characters_count: int = Field(ge=0)
    voice_mappings_count: int = Field(ge=0)
    runs_total_count: int = Field(ge=0)
    runs_completed_count: int = Field(ge=0)
    runs_failed_count: int = Field(ge=0)
    last_export_at: str | None = None


class ProjectActivityTimelineItem(BaseModel):
    event_id: int = Field(ge=1)
    event_type: ProjectActivityTimelineEventType
    actor: str = Field(min_length=1, max_length=255)
    run_id: int | None = Field(default=None, ge=1)
    created_at: str = Field(min_length=1)
    event_metadata: dict[str, object] = Field(default_factory=dict)


class ProjectActivityTimelineResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_activity_timeline_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-004")
    output_name: str = Field(default="project_activity_timeline")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_activity_timeline", min_length=1)
    project_id: int = Field(ge=1)
    total_items: int = Field(ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    has_next_page: bool = False
    items: list[ProjectActivityTimelineItem] = Field(default_factory=list)


ProjectLifecycleStateChangeAction = Literal["archive", "restore"]


class ProjectDetailResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_detail_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-005")
    output_name: str = Field(default="project_detail")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_detail", min_length=1)
    project_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    lifecycle_state: ProjectLifecycleState
    last_run_status: ProjectActionRunStatus | None = None
    next_required_action: ProjectControlPanelNextRequiredAction
    allowed_actions: list[ProjectAllowedAction] = Field(default_factory=list)
    selected_mode: str = Field(min_length=1, max_length=50)
    selected_modes: list[str] = Field(default_factory=list)
    llm_enabled: bool
    do_not_store_source_text: bool = False
    character_map_finalized: bool
    configuration_snapshot_id: str | None = None
    ingestion_timestamp: str | None = None
    last_export_at: str | None = None
    created_at: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)


class ProjectLifecycleStateChangeResponse(BaseModel):
    schema_version: str = Field(default="1.0.0")
    output_schema: str = Field(default="project_lifecycle_state_change_json")
    output_format: str = Field(default="json")
    output_id: str = Field(default="CP-006")
    output_name: str = Field(default="project_lifecycle_state_change")
    generated_at: str = Field(min_length=1)
    generated_by: str = Field(default="build_project_lifecycle_state_change", min_length=1)
    project_id: int = Field(ge=1)
    action: ProjectLifecycleStateChangeAction
    previous_lifecycle_state: ProjectLifecycleState
    lifecycle_state: ProjectLifecycleState
    last_run_status: ProjectActionRunStatus | None = None
    next_required_action: ProjectControlPanelNextRequiredAction
    allowed_actions: list[ProjectAllowedAction] = Field(default_factory=list)



class ComparisonWorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class ComparisonWorkspaceRunLinkRequest(BaseModel):
    project_id: int = Field(ge=1)
    run_id: int = Field(ge=1)


class ComparisonWorkspaceRunDescriptor(BaseModel):
    run_id: int
    project_id: int
    project_title: str
    status: RunStatus
    segment_count: int
    run_config_mode: str


class ComparisonWorkspaceResponse(BaseModel):
    workspace_id: int
    name: str
    description: str | None
    created_at: datetime
    run_count: int
    runs: list[ComparisonWorkspaceRunDescriptor]


class TensionGraphPoint(BaseModel):
    position: int = Field(ge=1)
    smoothed_tension: float = Field(ge=0.0, le=1.0)
    chapter_id: int | None = None
    segment_index: int | None = Field(default=None, ge=1)
    segment_id: str | None = None


class TensionGraphPeakMarker(BaseModel):
    position: int | None = None
    segment_id: str | None = None
    chapter_id: int | None = None
    segment_index: int | None = Field(default=None, ge=1)
    peak_type: str = Field(min_length=1)
    severity: str = Field(pattern=r"^(major|minor)$")
    prominence: float = Field(ge=0.0)
    previous_tension: float = Field(ge=0.0, le=1.0)
    next_tension: float = Field(ge=0.0, le=1.0)
    tension_value: float = Field(ge=0.0, le=1.0)


class TensionGraphValueRange(BaseModel):
    min: float = Field(ge=0.0, le=1.0)
    max: float = Field(ge=0.0, le=1.0)
    delta: float = Field(ge=0.0)


class TensionGraphPlateauRegion(BaseModel):
    region_type: str = Field(min_length=1)
    start_position: int | None = None
    end_position: int | None = None
    length: int = Field(ge=1)
    segment_count: int = Field(ge=1)
    segment_ids: list[str] = Field(default_factory=list)
    segment_indices: list[int] = Field(default_factory=list)
    chapter_ids: list[int] = Field(default_factory=list)
    average_tension: float = Field(ge=0.0, le=1.0)
    tension_value_range: TensionGraphValueRange


class TensionGraphContractResponse(BaseModel):
    metric_id: str = Field(pattern=r"^smoothed_tension_curve$")
    metric_label: str = Field(min_length=1)
    source_path: list[str]
    value_key: str = Field(pattern=r"^smoothed_tension$")
    points: list[TensionGraphPoint]
    peak_markers: list[TensionGraphPeakMarker]
    plateau_regions: list[TensionGraphPlateauRegion]
    metadata: dict[str, object] = Field(default_factory=dict)


class PolarityGraphPoint(BaseModel):
    position: int = Field(ge=1)
    rolling_mean_valence: float = Field(ge=-1.0, le=1.0)
    rolling_mean_intensity: float = Field(ge=0.0, le=1.0)
    chapter_id: int | None = None
    segment_index: int | None = Field(default=None, ge=1)
    segment_id: str | None = None


class PolarityGraphVolatilityMarker(BaseModel):
    position: int | None = None
    from_segment_id: str | None = None
    segment_id: str | None = None
    chapter_id: int | None = None
    segment_index: int | None = Field(default=None, ge=1)
    volatility_index: float = Field(ge=0.0, le=1.0)
    level: str = Field(min_length=1)
    valence_delta: float
    intensity_delta: float
    tension_delta: float
    dominance_delta: float
    triggers: list[str] = Field(default_factory=list)
    from_tension: float | None = None
    to_tension: float | None = None


class PolarityGraphResponse(BaseModel):
    metric_id: str = Field(pattern=r"^rolling_emotional_polarity$")
    metric_label: str = Field(min_length=1)
    source_path: list[str]
    value_key: str = Field(pattern=r"^rolling_mean_valence$")
    points: list[PolarityGraphPoint]
    volatility_markers: list[PolarityGraphVolatilityMarker]
    metadata: dict[str, object] = Field(default_factory=dict)


class ComparisonAlignedCurvePoint(BaseModel):
    normalized_position: float = Field(ge=0.0, le=1.0)
    value: float
    source_position: int | None = None


class ComparisonAlignedCurveRunDescriptor(BaseModel):
    run_id: int
    project_id: int
    project_title: str
    status: str
    points: list[ComparisonAlignedCurvePoint]


class ComparisonAlignedCurveMetricDescriptor(BaseModel):
    metric_id: str
    metric_label: str
    value_key: str
    source_path: list[str]
    points_per_run: list[ComparisonAlignedCurveRunDescriptor]


class ComparisonWorkspaceAlignedCurvesResponse(BaseModel):
    workspace_id: int
    workspace_name: str
    run_count: int
    aligned_points: int
    metrics: list[ComparisonAlignedCurveMetricDescriptor]


class ComparisonWorkspaceComparativeRunDescriptor(BaseModel):
    run_id: int
    project_id: int
    project_title: str
    status: str
    segment_count: int
    run_config_mode: str
    academic_reports: dict[str, Any]
    comparative_run_metrics_snapshot: dict[str, Any]
    academic_export_manifest: dict[str, Any]


class ComparisonWorkspaceComparativeExportResponse(BaseModel):
    workspace_id: int
    workspace_name: str
    generated_at: str
    run_count: int
    aligned_points: int
    metrics: list[ComparisonAlignedCurveMetricDescriptor]
    runs: list[ComparisonWorkspaceComparativeRunDescriptor]
