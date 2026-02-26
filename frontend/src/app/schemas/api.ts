import { z } from 'zod';

const defaultSpeakerConfidenceThreshold = 0.6;
const defaultHighAmbiguityDialogueFlagThreshold = 2;
const defaultUnstableEmotionShiftTransitionThreshold = 4;
const defaultUnstableEmotionShiftDensityThreshold = 0.5;
const defaultContradictionReviewRequired = true;
const ALLOWED_EXPORT_FORMATS = ['json', 'csv', 'time_series_json', 'graph_json'] as const;

const runExportFormatsSchema = z
  .array(z.string())
  .transform((formats) =>
    Array.from(
      new Set(
        formats
          .map((format) => format.trim().toLowerCase())
          .filter((format) => format.length > 0),
      ),
    ),
  )
  .superRefine((formats, context) => {
    if (formats.length === 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'export_formats must contain at least one value.',
        path: [],
      });
      return;
    }

    for (let index = 0; index < formats.length; index += 1) {
      const format = formats[index];
      if (!ALLOWED_EXPORT_FORMATS.includes(format as (typeof ALLOWED_EXPORT_FORMATS)[number])) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message:
            'export_formats must be one of: json, csv, time_series_json, graph_json',
          path: [index],
        });
      }
    }
  });

export const modeCatalogSchema = z.object({
  modes: z.array(z.string()),
  default_mode: z.string(),
  persisted_in: z.array(z.string()),
  mode_profiles: z.record(
    z.string(),
    z.object({
      max_segment_chars: z.number().int().min(80).max(255),
      llm_enabled: z.boolean(),
      export_formats: z
        .array(z.string())
        .transform((formats) =>
          Array.from(
            new Set(
              formats
                .map((format) => format.trim().toLowerCase())
                .filter((format) => format.length > 0),
            ),
          ),
        )
        .superRefine((formats, context) => {
          if (formats.length === 0) {
            context.addIssue({
              code: z.ZodIssueCode.custom,
              message: 'export_formats must contain at least one value.',
              path: [],
            });
            return;
          }

          for (let index = 0; index < formats.length; index += 1) {
            const format = formats[index];
            if (!ALLOWED_EXPORT_FORMATS.includes(format as (typeof ALLOWED_EXPORT_FORMATS)[number])) {
              context.addIssue({
                code: z.ZodIssueCode.custom,
                message:
                  'export_formats must be one of: json, csv, time_series_json, graph_json',
                path: [index],
              });
              break;
            }
          }
        }),
      export_chunk_size: z.number().int().min(1).max(10000),
      provider_name: z.string().min(1),
      max_calls_per_day: z.number().int().positive(),
      deterministic_mode: z.boolean(),
      speaker_confidence_threshold: z.number().min(0).max(1),
      high_ambiguity_dialogue_flag_threshold: z.number().int().min(1).max(20),
      unstable_emotion_shift_transition_threshold: z.number().int().min(1).max(20),
      unstable_emotion_shift_density_threshold: z.number().min(0).max(1),
      contradiction_review_required: z.boolean(),
      web_scraping_enabled: z.boolean(),
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
  do_not_store_source_text: z.boolean().default(false),
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
  voice_id: z.string().min(1).max(255).nullable().optional(),
  inferred_gender: characterGenderSchema.default("unknown"),
  inferred_confidence: z.number().min(0).max(1).default(0.0),
  inferred_source_trace: z.array(characterSourceTraceSchema).default([]),
  aliases: z.array(z.string()),
  notes: z.string().nullable(),
  source: z.string().min(1),
  confidence: z.number().min(0).max(1),
  source_trace: z.array(characterSourceTraceSchema).default([]),
});

export const characterWarningSchema = z.object({
  type: z.string().min(1),
  level: z.string().min(1),
  source: z.string().min(1),
  alias: z.string().min(1),
  canonical_names: z.array(z.string()),
  message: z.string().min(1),
  candidate_name: z.string().trim().transform((value) => value || undefined).nullable().optional(),
  confidence: z.number().min(0).max(1).nullable().optional(),
  threshold: z.number().min(0).max(1).nullable().optional(),
});

export const characterMapSchema = z.object({
  project_id: z.number().int(),
  characters: z.array(characterMapItemSchema),
  character_map_finalized: z.boolean(),
});

export const characterGenderComparisonItemSchema = z.object({
  name: z.string().min(1),
  manual_gender: characterGenderSchema,
  inferred_gender: characterGenderSchema,
  manual_confidence: z.number().min(0).max(1),
  inferred_confidence: z.number().min(0).max(1),
  comparison: z.string().min(1),
  contradiction_severity: z.number().min(0).max(1),
  is_contradiction: z.boolean(),
  requires_review: z.boolean(),
});

export const characterGenderWarningItemSchema = z.object({
  type: z.string().min(1),
  level: z.string().min(1),
  source: z.string().min(1),
  character_name: z.string().min(1),
  manual_gender: characterGenderSchema,
  inferred_gender: characterGenderSchema,
  manual_confidence: z.number().min(0).max(1),
  inferred_confidence: z.number().min(0).max(1),
  contradiction_severity: z.number().min(0).max(1),
  requires_review: z.boolean(),
  message: z.string().min(1),
});

export const characterGenderComparisonResponseSchema = z.object({
  project_id: z.number().int(),
  comparison_count: z.number().int().nonnegative(),
  contradiction_count: z.number().int().nonnegative(),
  comparisons: z.array(characterGenderComparisonItemSchema),
  warnings: z.array(characterGenderWarningItemSchema).default([]),
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
  warnings: z.array(characterWarningSchema).optional().default([]),
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
  export_formats: runExportFormatsSchema.optional(),
  export_chunk_size: z.number().int().min(1).max(10000).optional(),
  speaker_confidence_threshold: z.number().min(0).max(1).default(defaultSpeakerConfidenceThreshold),
  high_ambiguity_dialogue_flag_threshold: z.number().int().min(1).max(20).default(defaultHighAmbiguityDialogueFlagThreshold),
  unstable_emotion_shift_transition_threshold: z.number().int().min(1).max(20).default(defaultUnstableEmotionShiftTransitionThreshold),
  unstable_emotion_shift_density_threshold: z
    .number()
    .min(0)
    .max(1)
    .default(defaultUnstableEmotionShiftDensityThreshold),
  contradiction_review_required: z.boolean().default(defaultContradictionReviewRequired),
  deterministic_mode: z.boolean().default(false),
  deterministic_model_identifier: z.string().trim().transform((value) => value || undefined).optional(),
  deterministic_seed: z.number().int().min(0).optional(),
  randomization_config: z
    .object({
      seed: z.number().int().min(0).optional(),
      strategy: z.string().min(1).optional(),
      shuffle_enabled: z.boolean().optional(),
    })
    .optional(),
  web_scraping_enabled: z.boolean().default(false),
  emotion_taxonomy: z.enum(['basic', 'expanded']).default('basic'),
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
  changelog_entries: z
    .array(
      z.object({
        id: z.number().int(),
        event_type: z.string(),
        event_message: z.string().nullable(),
        event_metadata: z.record(z.string(), z.unknown()),
        created_at: z.string(),
      }),
    )
    .default([]),
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

export const runConfigFieldDiffSchema = z.object({
  field: z.string().min(1),
  base_value: z.unknown().nullable().optional(),
  target_value: z.unknown().nullable().optional(),
});

export const runConfigDiffResponseSchema = z.object({
  project_id: z.number().int().positive(),
  base_run_id: z.number().int().positive(),
  target_run_id: z.number().int().positive(),
  base_config_schema_version: z.string().min(1),
  target_config_schema_version: z.string().min(1),
  is_identical: z.boolean(),
  changed_fields: z.array(runConfigFieldDiffSchema),
  base_only_fields: z.array(z.string()),
  target_only_fields: z.array(z.string()),
});

export const runConfigPresetResponseSchema = z.object({
  project_id: z.number().int().positive(),
  run_id: z.number().int().positive(),
  preset_schema_version: z.string().min(1),
  generated_at: z.string().min(1),
  run_config: runRequestSchema.partial(),
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
  metadata: z.record(z.string(), z.unknown()).default({}),
});

export const characterMentionsByChapterItemSchema = z.object({
  chapter_index: z.number().int().positive(),
  mention_counts: z.record(z.number().int().nonnegative()),
});

export const characterAnalyticsResponseSchema = z.object({
  project_id: z.number().int().positive(),
  run_id: z.number().int().positive(),
  character_mentions_by_chapter: z.array(characterMentionsByChapterItemSchema),
  character_first_appearance_chapter_index: z.record(z.number().int().positive().nullable()),
  character_last_appearance_chapter_index: z.record(z.number().int().positive().nullable()),
  character_mentions_per_1000_words: z.record(z.number().nonnegative()),
  character_dialogue_line_counts: z.record(z.number().int().nonnegative()),
});

export const characterCooccurrenceGraphNodeSchema = z.object({
  character_key: z.string().min(1),
  character_label: z.string().min(1),
  speaker_id: z.number().int().nonnegative().nullable().optional().default(null),
  segment_count: z.number().int().nonnegative(),
  chapter_ids: z.array(z.number().int().positive()),
  chapter_count: z.number().int().nonnegative(),
  adjacency_weight: z.number().int().nonnegative(),
});

export const characterCooccurrenceGraphEdgeSchema = z.object({
  source: z.string().min(1),
  target: z.string().min(1),
  co_occurrence_count: z.number().int().nonnegative(),
  weight: z.number().int().nonnegative(),
  chapter_ids: z.array(z.number().int().positive()),
  chapter_count: z.number().int().nonnegative(),
});

export const characterCooccurrenceGraphMetadataSchema = z.object({
  node_count: z.number().int().nonnegative(),
  edge_count: z.number().int().nonnegative(),
  scope: z.string(),
  undirected: z.boolean(),
  generated_by: z.string(),
});

export const characterCooccurrenceGraphDataSchema = z.object({
  nodes: z.array(characterCooccurrenceGraphNodeSchema),
  edges: z.array(characterCooccurrenceGraphEdgeSchema),
  metadata: characterCooccurrenceGraphMetadataSchema,
});

export const characterCooccurrenceCentralityMetadataSchema = z.object({
  node_count: z.number().int().nonnegative(),
  edge_count: z.number().int().nonnegative(),
  distance_transform: z.string().nullable().optional(),
  generated_by: z.string(),
  centrality_metrics: z.array(z.string()),
});

export const characterCooccurrenceCentralityRowSchema = z.object({
  character_key: z.string().min(1),
  character_label: z.string().min(1),
  speaker_id: z.number().int().nonnegative().nullable().optional().default(null),
  rank: z.number().int().positive(),
  degree: z.number().int().nonnegative(),
  weighted_degree: z.number().nonnegative(),
  degree_centrality: z.number().min(0).max(1),
  weighted_degree_centrality: z.number().min(0).max(1),
  closeness_centrality: z.number().min(0).max(1),
  betweenness_centrality: z.number().min(0).max(1),
});

export const characterCooccurrenceCentralityPayloadSchema = z.object({
  metrics_table: z.array(characterCooccurrenceCentralityRowSchema),
  metadata: characterCooccurrenceCentralityMetadataSchema,
});

export const characterCooccurrenceGraphResponseSchema = z.object({
  schema_version: z.string(),
  output_schema: z.string(),
  output_format: z.string(),
  output_id: z.string(),
  output_name: z.string(),
  project_id: z.number().int(),
  run_id: z.number().int(),
  run_status: z.string(),
  generated_at: z.string(),
  generated_by: z.string(),
  graph: characterCooccurrenceGraphDataSchema,
  character_cooccurrence_centrality: characterCooccurrenceCentralityPayloadSchema,
  manifest_snapshot: z.record(z.string(), z.unknown()),
});

export const polarityGraphPointSchema = z.object({
  position: z.number().int().positive(),
  rolling_mean_valence: z.number().min(-1).max(1),
  rolling_mean_intensity: z.number().min(0).max(1),
  chapter_id: z.number().int().nonnegative().nullable().optional().default(null),
  segment_index: z.number().int().positive().nullable().optional().default(null),
  segment_id: z.string().nullable().optional().default(null),
});

export const polarityGraphVolatilityMarkerSchema = z.object({
  position: z.number().int().positive().nullable().optional().default(null),
  from_segment_id: z.string().nullable().optional().default(null),
  segment_id: z.string().nullable().optional().default(null),
  chapter_id: z.number().int().nonnegative().nullable().optional().default(null),
  segment_index: z.number().int().positive().nullable().optional().default(null),
  volatility_index: z.number().min(0),
  level: z.string(),
  valence_delta: z.number(),
  intensity_delta: z.number(),
  tension_delta: z.number(),
  dominance_delta: z.number(),
  triggers: z.array(z.string()).default([]),
  from_tension: z.number().nullable().optional().default(null),
  to_tension: z.number().nullable().optional().default(null),
});

export const polarityGraphResponseSchema = z.object({
  metric_id: z.string(),
  metric_label: z.string().min(1),
  source_path: z.array(z.string()),
  value_key: z.string(),
  points: z.array(polarityGraphPointSchema),
  volatility_markers: z.array(polarityGraphVolatilityMarkerSchema),
  metadata: z.record(z.string(), z.unknown()).default({}),
});

export const audiobookPrepDashboardReadinessSchema = z.object({
  is_ready: z.boolean(),
  blocking_reasons: z.array(z.string()),
  warning_reasons: z.array(z.string()),
});

export const audiobookPrepDashboardResponseSchema = z.object({
  schema_version: z.string(),
  output_schema: z.string(),
  output_format: z.string(),
  output_id: z.string(),
  output_name: z.string(),
  project_id: z.number().int().nonnegative(),
  run_id: z.number().int().nonnegative(),
  run_status: z.string(),
  generated_at: z.string(),
  generated_by: z.string(),
  unresolved_speaker_count: z.number().int().nonnegative(),
  unresolved_voice_mapping_count: z.number().int().nonnegative(),
  low_confidence_region_count: z.number().int().nonnegative(),
  export_readiness: audiobookPrepDashboardReadinessSchema,
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
export type CharacterGenderComparisonItemDto = z.infer<typeof characterGenderComparisonItemSchema>;
export type CharacterGenderComparisonResponseDto = z.infer<typeof characterGenderComparisonResponseSchema>;
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
export type RunConfigFieldDiffDto = z.infer<typeof runConfigFieldDiffSchema>;
export type RunConfigDiffResponseDto = z.infer<typeof runConfigDiffResponseSchema>;
export type RunConfigPresetResponseDto = z.infer<typeof runConfigPresetResponseSchema>;
export type ExportDto = z.infer<typeof exportSchema>;
export type TensionGraphPointDto = z.infer<typeof tensionGraphPointSchema>;
export type TensionGraphPeakMarkerDto = z.infer<typeof tensionGraphPeakMarkerSchema>;
export type TensionGraphPlateauRegionDto = z.infer<typeof tensionGraphPlateauRegionSchema>;
export type TensionGraphResponseDto = z.infer<typeof tensionGraphResponseSchema>;
export type PolarityGraphPointDto = z.infer<typeof polarityGraphPointSchema>;
export type PolarityGraphVolatilityMarkerDto = z.infer<typeof polarityGraphVolatilityMarkerSchema>;
export type PolarityGraphResponseDto = z.infer<typeof polarityGraphResponseSchema>;
export type AudiobookPrepDashboardReadinessDto = z.infer<typeof audiobookPrepDashboardReadinessSchema>;
export type AudiobookPrepDashboardResponseDto = z.infer<typeof audiobookPrepDashboardResponseSchema>;
export type CharacterMentionsByChapterItemDto = z.infer<typeof characterMentionsByChapterItemSchema>;
export type CharacterAnalyticsResponseDto = z.infer<typeof characterAnalyticsResponseSchema>;
export type CharacterCooccurrenceGraphNodeDto = z.infer<typeof characterCooccurrenceGraphNodeSchema>;
export type CharacterCooccurrenceGraphEdgeDto = z.infer<typeof characterCooccurrenceGraphEdgeSchema>;
export type CharacterCooccurrenceGraphDataDto = z.infer<typeof characterCooccurrenceGraphDataSchema>;
export type CharacterCooccurrenceCentralityRowDto = z.infer<typeof characterCooccurrenceCentralityRowSchema>;
export type CharacterCooccurrenceCentralityPayloadDto = z.infer<typeof characterCooccurrenceCentralityPayloadSchema>;
export type CharacterCooccurrenceGraphResponseDto = z.infer<typeof characterCooccurrenceGraphResponseSchema>;
