import { z } from 'zod';

export const modeCatalogSchema = z.object({
  modes: z.array(z.string()),
  default_mode: z.string(),
  persisted_in: z.array(z.string()),
  mode_profiles: z.record(
    z.string(),
    z.object({
      max_segment_chars: z.number().int().min(80).max(255),
      llm_enabled: z.boolean(),
      provider_name: z.string().min(1),
      max_calls_per_day: z.number().int().positive(),
      deterministic_mode: z.boolean(),
      profile_intent: z.string().min(1),
    }),
  ),
});

export const projectSchema = z.object({
  id: z.number().int(),
  title: z.string(),
  selected_mode: z.string(),
  selected_modes: z.array(z.string()),
  llm_enabled: z.boolean(),
  configuration_snapshot_id: z.string().nullable(),
  ingestion_timestamp: z.string().nullable(),
  created_at: z.string(),
});

export const projectLLMSettingsRequestSchema = z.object({
  llm_enabled: z.boolean(),
});

export const projectLLMSettingsResponseSchema = z.object({
  project_id: z.number().int(),
  llm_enabled: z.boolean(),
});

export const llmTaskTypeSchema = z.enum([
  'sentiment_probe',
  'emotion_refinement',
  'speaker_resolution',
  'character_extraction',
  'edge_case_structural_interpretation',
  'scene_classification',
]);

export const projectModeSwitchResponseSchema = z.object({
  project_id: z.number().int(),
  previous_mode: z.string(),
  selected_mode: z.string(),
  selected_modes: z.array(z.string()),
  chapter_count: z.number().int().nonnegative(),
  reused_ingested_corpus: z.boolean(),
  stale_runs_marked: z.number().int().nonnegative(),
});

export const ingestResponseSchema = z.object({
  project_id: z.number().int(),
  chapter_count: z.number().int().nonnegative(),
});

export const characterImportSchema = z.object({
  project_id: z.number().int(),
  imported_count: z.number().int().nonnegative(),
});

export const characterSourceTraceSchema = z.object({
  kind: z.string().min(1),
  chapter_index: z.number().int().positive(),
  span_start: z.number().int().nonnegative(),
  span_end: z.number().int().nonnegative(),
  excerpt: z.string().min(1),
  weight: z.number().min(0).max(1),
});

export const characterGenderSchema = z.enum(['male', 'female', 'neutral', 'unknown', 'custom']);

export const characterMapItemSchema = z.object({
  name: z.string().min(1),
  verbalized_form: z.string().min(1),
  gender: characterGenderSchema,
  aliases: z.array(z.string()),
  notes: z.string().nullable(),
  source: z.string().min(1),
  confidence: z.number().min(0).max(1),
  source_trace: z.array(characterSourceTraceSchema).default([]),
});

export const characterMapSchema = z.object({
  project_id: z.number().int(),
  characters: z.array(characterMapItemSchema),
  character_map_finalized: z.boolean(),
});

export const characterMapUpdateSchema = z.object({
  characters: z.array(characterMapItemSchema),
});

export const characterMapFinalizeSchema = z.object({
  project_id: z.number().int(),
  character_map_finalized: z.boolean(),
});

export const characterScrapeRequestSchema = z.object({
  source_url: z.string().min(1).max(2048).url(),
  acknowledge_source_risk: z.boolean(),
});

export const characterCandidatesMergeRequestSchema = z.object({
  include_auto: z.boolean(),
  source_url: z.string().max(2048).url().optional(),
  acknowledge_source_risk: z.boolean(),
});

export const pronunciationDictionaryPreviewItemSchema = z.object({
  term: z.string().min(1),
  verbalized_form: z.string().min(1),
  count: z.number().int().nonnegative(),
  scope: z.string().min(1),
});

export const pronunciationDictionaryPreviewWarningSchema = z.object({
  type: z.string().min(1),
  term: z.string().min(1),
  message: z.string().min(1),
  scopes: z.array(z.string()),
  competing_verbalized_forms: z.array(z.string()),
});

export const pronunciationDictionaryPreviewRequestSchema = z.object({
  text: z.string().min(1).max(10000),
  character_name: z.string().trim().transform((value) => value || undefined).optional(),
  include_global_scope: z.boolean().default(true),
  include_character_scope: z.boolean().default(true),
  include_place_scope: z.boolean().default(false),
  include_artifact_scope: z.boolean().default(false),
  include_invented_scope: z.boolean().default(false),
  match_whole_words: z.boolean().default(true),
  case_sensitive: z.boolean().default(true),
  alias_aware: z.boolean().default(false),
});

export const pronunciationDictionaryPreviewResponseSchema = z.object({
  project_id: z.number().int(),
  before: z.string(),
  after: z.string(),
  character_name: z.string().nullable(),
  replacements: z.array(pronunciationDictionaryPreviewItemSchema).default([]),
  included_scopes: z.array(z.string()),
  warnings: z.array(pronunciationDictionaryPreviewWarningSchema).optional().default([]),
});

export const characterExtractionSchema = z.object({
  project_id: z.number().int(),
  status: z.string(),
  candidate_count: z.number().int().nonnegative(),
  candidates: z.array(characterMapItemSchema),
  proposed_characters: z.array(characterMapItemSchema).default([]),
  canonical_merge_suggestions: z
    .array(
      z.object({
        canonical_name: z.string().min(1),
        alias_name: z.string().min(1),
        score: z.number().min(0).max(1),
        candidate_source: z.string(),
        canonical_source: z.string(),
        reason: z.string().min(1),
      }),
    )
    .default([]),
});

export const voiceConfigSchema = z.object({
  narrator_voice: z.string(),
  male_default_voice: z.string(),
  female_default_voice: z.string(),
  neutral_default_voice: z.string(),
  unknown_default_voice: z.string(),
  internal_thought_voice_policy: z.enum(['character', 'narrator', 'thought_voice']),
  internal_thought_voice: z.string().trim().transform((value) => value || undefined).optional(),
});

export const voiceConfigResponseSchema = z.object({
  project_id: z.number().int(),
  voice_config: voiceConfigSchema,
});

export const runRequestSchema = z.object({
  mode: z.string(),
  max_segment_chars: z.number().int().min(80).max(255),
  llm_enabled: z.boolean(),
  provider_name: z.string(),
  deterministic_mode: z.boolean().default(false),
  max_calls_per_day: z.number().int().positive(),
  allow_unfinalized_character_map: z.boolean().default(false),
  internal_thought_voice_policy: z.enum(['character', 'narrator', 'thought_voice']).default('character'),
  internal_thought_voice: z.string().trim().transform((value) => value || undefined).optional(),
});

export const runResponseSchema = z.object({
  run_id: z.number().int(),
  project_id: z.number().int(),
  status: z.string(),
  segment_count: z.number().int().nonnegative(),
});

const llmCacheMetricsSchema = z.record(
  z.object({
    hits: z.number().int().nonnegative(),
    misses: z.number().int().nonnegative(),
  }),
);

export const runDetailSchema = z.object({
  run_id: z.number().int(),
  project_id: z.number().int(),
  status: z.string(),
  config: z.record(z.string(), z.unknown()),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  segment_count: z.number().int().nonnegative(),
  llm_calls: z.array(
    z.object({
      id: z.number().int(),
      provider: z.string(),
      task_type: llmTaskTypeSchema,
      success: z.boolean(),
      request_count: z.number().int(),
      is_cache_hit: z.boolean(),
      detail: z.string().nullable(),
      created_at: z.string(),
    }),
  ),
  llm_cache_metrics: llmCacheMetricsSchema.default({}),
});

export type LLMTaskType = z.infer<typeof llmTaskTypeSchema>;

export const exportSchema = z.object({
  project_id: z.number().int(),
  project_title: z.string(),
  run_id: z.number().int(),
  status: z.string(),
  segments: z.array(z.record(z.string(), z.unknown())),
});

export const tensionGraphPointSchema = z.object({
  position: z.number().int().positive(),
  smoothed_tension: z.number().min(0).max(1),
  chapter_id: z.number().int().nonnegative().nullable().optional().default(null),
  segment_index: z.number().int().positive().nullable().optional().default(null),
  segment_id: z.string().nullable().optional().default(null),
});

export const tensionGraphPeakMarkerSchema = z.object({
  position: z.number().int().positive().nullable().optional().default(null),
  segment_id: z.string().nullable().optional().default(null),
  chapter_id: z.number().int().nonnegative().nullable().optional().default(null),
  segment_index: z.number().int().positive().nullable().optional().default(null),
  peak_type: z.string(),
  severity: z.string(),
  prominence: z.number().min(0),
  previous_tension: z.number().min(0).max(1),
  next_tension: z.number().min(0).max(1),
  tension_value: z.number().min(0).max(1),
});

export const tensionGraphValueRangeSchema = z.object({
  min: z.number().min(0).max(1),
  max: z.number().min(0).max(1),
  delta: z.number().min(0),
});

export const tensionGraphPlateauRegionSchema = z.object({
  region_type: z.string(),
  start_position: z.number().int().nullable().optional().default(null),
  end_position: z.number().int().nullable().optional().default(null),
  length: z.number().int().positive(),
  segment_count: z.number().int().positive(),
  segment_ids: z.array(z.string()).default([]),
  segment_indices: z.array(z.number().int().positive()).default([]),
  chapter_ids: z.array(z.number().int().positive()).default([]),
  average_tension: z.number().min(0).max(1),
  tension_value_range: tensionGraphValueRangeSchema,
});

export const tensionGraphResponseSchema = z.object({
  metric_id: z.string(),
  metric_label: z.string().min(1),
  source_path: z.array(z.string()),
  value_key: z.string(),
  points: z.array(tensionGraphPointSchema),
  peak_markers: z.array(tensionGraphPeakMarkerSchema),
  plateau_regions: z.array(tensionGraphPlateauRegionSchema),
  metadata: z.record(z.unknown()).default({}),
});

export type ModeCatalogDto = z.infer<typeof modeCatalogSchema>;
export type ProjectDto = z.infer<typeof projectSchema>;
export type ProjectLLMSettingsRequestDto = z.infer<typeof projectLLMSettingsRequestSchema>;
export type ProjectLLMSettingsResponseDto = z.infer<typeof projectLLMSettingsResponseSchema>;
export type ProjectModeSwitchResponseDto = z.infer<typeof projectModeSwitchResponseSchema>;
export type IngestResponseDto = z.infer<typeof ingestResponseSchema>;
export type CharacterImportDto = z.infer<typeof characterImportSchema>;
export type CharacterMapItemDto = z.infer<typeof characterMapItemSchema>;
export type CharacterMapDto = z.infer<typeof characterMapSchema>;
export type CharacterMapUpdateDto = z.infer<typeof characterMapUpdateSchema>;
export type CharacterMapFinalizeDto = z.infer<typeof characterMapFinalizeSchema>;
export type CharacterScrapeRequestDto = z.infer<typeof characterScrapeRequestSchema>;
export type CharacterCandidatesMergeRequestDto = z.infer<typeof characterCandidatesMergeRequestSchema>;
export type PronunciationDictionaryPreviewItemDto = z.infer<typeof pronunciationDictionaryPreviewItemSchema>;
export type PronunciationDictionaryPreviewWarningDto = z.infer<typeof pronunciationDictionaryPreviewWarningSchema>;
export type PronunciationDictionaryPreviewRequestDto = z.infer<typeof pronunciationDictionaryPreviewRequestSchema>;
export type PronunciationDictionaryPreviewResponseDto = z.infer<typeof pronunciationDictionaryPreviewResponseSchema>;
export type CharacterExtractionDto = z.infer<typeof characterExtractionSchema>;
export type VoiceConfigDto = z.infer<typeof voiceConfigSchema>;
export type RunRequestDto = z.infer<typeof runRequestSchema>;
export type RunResponseDto = z.infer<typeof runResponseSchema>;
export type RunDetailDto = z.infer<typeof runDetailSchema>;
export type ExportDto = z.infer<typeof exportSchema>;
export type TensionGraphPointDto = z.infer<typeof tensionGraphPointSchema>;
export type TensionGraphPeakMarkerDto = z.infer<typeof tensionGraphPeakMarkerSchema>;
export type TensionGraphPlateauRegionDto = z.infer<typeof tensionGraphPlateauRegionSchema>;
export type TensionGraphResponseDto = z.infer<typeof tensionGraphResponseSchema>;
