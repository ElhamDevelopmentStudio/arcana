import { z } from "zod";

export const modeCatalogSchema = z.object({
  modes: z.array(z.string()).min(1),
  default_mode: z.string().min(1),
  persisted_in: z.array(z.string()),
});

export const projectResponseSchema = z.object({
  id: z.number().int().positive(),
  title: z.string().min(1),
  selected_mode: z.string().min(1),
  created_at: z.string().min(1),
});

export const ingestResponseSchema = z.object({
  project_id: z.number().int().positive(),
  chapter_count: z.number().int().nonnegative(),
});

export const characterImportResponseSchema = z.object({
  project_id: z.number().int().positive(),
  imported_count: z.number().int().nonnegative(),
});

export const runResponseSchema = z.object({
  run_id: z.number().int().positive(),
  project_id: z.number().int().positive(),
  status: z.string().min(1),
  segment_count: z.number().int().nonnegative(),
});

const llmCallSchema = z.object({
  id: z.number().int().positive(),
  provider: z.string(),
  task_type: z.string(),
  success: z.boolean(),
  request_count: z.number().int().nonnegative(),
  detail: z.string().nullable(),
  created_at: z.string(),
});

export const runDetailSchema = z.object({
  run_id: z.number().int().positive(),
  project_id: z.number().int().positive(),
  status: z.string(),
  config: z.record(z.string(), z.unknown()),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  segment_count: z.number().int().nonnegative(),
  llm_calls: z.array(llmCallSchema),
});

export const exportPayloadSchema = z.object({
  project_id: z.number().int().positive(),
  project_title: z.string(),
  run_id: z.number().int().positive(),
  status: z.string(),
  segments: z.array(z.record(z.string(), z.unknown())),
});

export type ModeCatalogSchema = z.infer<typeof modeCatalogSchema>;
export type ProjectResponseSchema = z.infer<typeof projectResponseSchema>;
export type IngestResponseSchema = z.infer<typeof ingestResponseSchema>;
export type CharacterImportResponseSchema = z.infer<typeof characterImportResponseSchema>;
export type RunResponseSchema = z.infer<typeof runResponseSchema>;
export type RunDetailSchema = z.infer<typeof runDetailSchema>;
export type ExportPayloadSchema = z.infer<typeof exportPayloadSchema>;
