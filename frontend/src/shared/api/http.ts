import axios, { AxiosError, type AxiosInstance } from "axios";

import {
  characterImportResponseSchema,
  exportPayloadSchema,
  ingestResponseSchema,
  modeCatalogSchema,
  projectResponseSchema,
  runDetailSchema,
  runResponseSchema,
} from "@/app/schemas/api";

export type RunPayload = {
  mode: string;
  max_segment_chars: number;
  llm_enabled: boolean;
  provider_name: string;
  max_calls_per_day: number;
};

export type VoicePayload = {
  narrator_voice: string;
  male_default_voice: string;
  female_default_voice: string;
};

function toApiError(error: unknown): Error {
  if (error instanceof AxiosError) {
    const detail = error.response?.data;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return new Error(detail);
    }

    if (detail && typeof detail === "object" && "detail" in detail && typeof detail.detail === "string") {
      return new Error(detail.detail);
    }

    if (error.message) {
      return new Error(error.message);
    }
  }

  if (error instanceof Error) {
    return error;
  }

  return new Error("Unexpected API error");
}

export class NipeApiClient {
  private readonly http: AxiosInstance;

  readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    this.http = axios.create({
      baseURL: baseUrl,
      timeout: 30_000,
    });
  }

  async getModeCatalog() {
    try {
      const response = await this.http.get("/api/modes");
      return modeCatalogSchema.parse(response.data);
    } catch (error) {
      throw toApiError(error);
    }
  }

  async createProject(title: string) {
    try {
      const response = await this.http.post("/api/projects", { title });
      return projectResponseSchema.parse(response.data);
    } catch (error) {
      throw toApiError(error);
    }
  }

  async ingestTxt(projectId: number, file: File) {
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await this.http.post(`/api/projects/${projectId}/ingest/txt`, form);
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw toApiError(error);
    }
  }

  async importCharacters(projectId: number, file: File) {
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await this.http.post(`/api/projects/${projectId}/characters/import`, form);
      return characterImportResponseSchema.parse(response.data);
    } catch (error) {
      throw toApiError(error);
    }
  }

  async saveVoices(projectId: number, payload: VoicePayload) {
    try {
      await this.http.put(`/api/projects/${projectId}/voices`, payload);
    } catch (error) {
      throw toApiError(error);
    }
  }

  async runPipeline(projectId: number, payload: RunPayload) {
    try {
      const response = await this.http.post(`/api/projects/${projectId}/runs`, payload);
      return runResponseSchema.parse(response.data);
    } catch (error) {
      throw toApiError(error);
    }
  }

  async getRunDetail(projectId: number, runId: number) {
    try {
      const response = await this.http.get(`/api/projects/${projectId}/runs/${runId}`);
      return runDetailSchema.parse(response.data);
    } catch (error) {
      throw toApiError(error);
    }
  }

  async getExport(projectId: number, runId: number) {
    try {
      const response = await this.http.get(`/api/projects/${projectId}/exports/${runId}.json`);
      return exportPayloadSchema.parse(response.data);
    } catch (error) {
      throw toApiError(error);
    }
  }
}
