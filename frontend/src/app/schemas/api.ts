import { z } from 'zod';

export const modeCatalogSchema = z.object({
  modes: z.array(z.string()),
  default_mode: z.string(),
  persisted_in: z.array(z.string()),
});

export const projectSchema = z.object({
  id: z.number().int(),
  title: z.string(),
  selected_mode: z.string(),
  created_at: z.string(),
});

export const ingestResponseSchema = z.object({
  project_id: z.number().int(),
  chapter_count: z.number().int().nonnegative(),
});

export const characterImportSchema = z.object({
  project_id: z.number().int(),
  imported_count: z.number().int().nonnegative(),
});

export const voiceConfigSchema = z.object({
  narrator_voice: z.string(),
  male_default_voice: z.string(),
  female_default_voice: z.string(),
});

export const voiceConfigResponseSchema = z.object({
  project_id: z.number().int(),
  voice_config: voiceConfigSchema,
});

export const runRequestSchema = z.object({
  mode: z.string(),
  max_segment_chars: z.number().int().positive(),
  llm_enabled: z.boolean(),
  provider_name: z.string(),
  max_calls_per_day: z.number().int().positive(),
});

export const runResponseSchema = z.object({
  run_id: z.number().int(),
  project_id: z.number().int(),
  status: z.string(),
  segment_count: z.number().int().nonnegative(),
});

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
      task_type: z.string(),
      success: z.boolean(),
      request_count: z.number().int(),
      detail: z.string().nullable(),
      created_at: z.string(),
    }),
  ),
});

export const exportSchema = z.object({
  project_id: z.number().int(),
  project_title: z.string(),
  run_id: z.number().int(),
  status: z.string(),
  segments: z.array(z.record(z.string(), z.unknown())),
});

export type ModeCatalogDto = z.infer<typeof modeCatalogSchema>;
export type ProjectDto = z.infer<typeof projectSchema>;
export type IngestResponseDto = z.infer<typeof ingestResponseSchema>;
export type CharacterImportDto = z.infer<typeof characterImportSchema>;
export type VoiceConfigDto = z.infer<typeof voiceConfigSchema>;
export type RunRequestDto = z.infer<typeof runRequestSchema>;
export type RunResponseDto = z.infer<typeof runResponseSchema>;
export type RunDetailDto = z.infer<typeof runDetailSchema>;
export type ExportDto = z.infer<typeof exportSchema>;
