export type ModeValue = "audiobook" | "academic" | "author" | "custom" | string;

export type RunDetail = {
  run_id: number;
  project_id: number;
  status: string;
  config: Record<string, unknown>;
  started_at: string;
  finished_at: string | null;
  segment_count: number;
  llm_calls: Array<{
    id: number;
    provider: string;
    task_type: string;
    success: boolean;
    request_count: number;
    detail: string | null;
    created_at: string;
  }>;
};

export type ExportPayload = {
  project_id: number;
  project_title: string;
  run_id: number;
  status: string;
  segments: Array<Record<string, unknown>>;
};

export type ModeCatalog = {
  modes: string[];
  default_mode: string;
  persisted_in: string[];
};

export type ProjectRecord = {
  id: number;
  title: string;
  selected_mode: string;
  created_at: string;
};

export type IngestionSource = "txt" | "directory" | "markdown" | "epub";
