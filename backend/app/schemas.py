from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.modes import DEFAULT_MODE, is_valid_mode


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ProjectResponse(BaseModel):
    id: int
    title: str
    selected_mode: str
    selected_modes: list[str]
    llm_enabled: bool
    configuration_snapshot_id: str | None
    character_map_finalized: bool
    ingestion_timestamp: datetime | None
    created_at: datetime


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
    llm_enabled: bool
    provider_name: str = Field(min_length=1)
    max_calls_per_day: int = Field(ge=1, le=10000)
    llm_confidence_threshold: float = Field(ge=0.0, le=1.0)
    deep_semantic_refinement: bool
    deterministic_mode: bool
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


class CharacterGenderComparisonResponse(BaseModel):
    project_id: int
    comparison_count: int
    contradiction_count: int
    comparisons: list[CharacterGenderComparisonItem]


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
    max_segment_chars: int = Field(default=255, ge=80, le=255)
    llm_enabled: bool = False
    provider_name: str = "openrouter"
    deep_semantic_refinement: bool = False
    deterministic_mode: bool = False
    max_calls_per_day: int = Field(default=25, ge=1, le=10000)
    llm_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    deterministic_model_identifier: str | None = None
    deterministic_seed: int | None = Field(default=None, ge=0)
    randomization_config: dict[str, object] | None = None
    provider_api_keys: dict[str, list[str]] | None = None
    allow_unfinalized_character_map: bool = False
    internal_thought_voice_policy: str = "character"
    internal_thought_voice: str | None = None

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
    status: str
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


class LLMCacheMetrics(BaseModel):
    hits: int = Field(ge=0)
    misses: int = Field(ge=0)


class RunDetailResponse(BaseModel):
    run_id: int
    project_id: int
    status: str
    config: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None
    segment_count: int
    llm_cache_metrics: dict[str, LLMCacheMetrics] = Field(default_factory=dict)
    llm_calls: list[RunLLMCallLog]


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
    status: str
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
