import axios, { AxiosError, type AxiosInstance } from 'axios';

import { appEnv } from '@/app/config/env';
import {
  characterImportSchema,
  characterAnalyticsResponseSchema,
  characterCooccurrenceGraphResponseSchema,
  characterMapSchema,
  characterMapUpdateSchema,
  characterMapFinalizeSchema,
  characterCandidatesMergeRequestSchema,
  characterScrapeRequestSchema,
  pronunciationDictionaryPreviewRequestSchema,
  pronunciationDictionaryPreviewResponseSchema,
  audiobookPrepDashboardResponseSchema,
  exportSchema,
  tensionGraphResponseSchema,
  ingestResponseSchema,
  modeCatalogSchema,
  projectSchema,
  projectLLMSettingsRequestSchema,
  projectLLMSettingsResponseSchema,
  projectModeSwitchResponseSchema,
  runDetailSchema,
  runConfigDiffResponseSchema,
  runRequestSchema,
  runResponseSchema,
  characterGenderComparisonResponseSchema,
  voiceConfigResponseSchema,
  type RunRequestDto,
  type RunConfigDiffResponseDto,
  type ProjectLLMSettingsRequestDto,
  type ProjectLLMSettingsResponseDto,
  type VoiceConfigDto,
  type CharacterMapDto,
  type CharacterMapUpdateDto,
  type CharacterMapFinalizeDto,
  type CharacterScrapeRequestDto,
  type CharacterCandidatesMergeRequestDto,
  type CharacterAnalyticsResponseDto,
  type CharacterCooccurrenceGraphResponseDto,
  type CharacterExtractionDto,
  type CharacterGenderComparisonResponseDto,
  type PronunciationDictionaryPreviewRequestDto,
  type PronunciationDictionaryPreviewResponseDto,
  type AudiobookPrepDashboardResponseDto,
  type TensionGraphResponseDto,
  characterExtractionSchema,
} from '@/app/schemas/api';

function normalizeHttpError(error: unknown): Error {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    const fieldErrorsRaw = error.response?.data?.field_errors;
    const fieldErrors = Array.isArray(fieldErrorsRaw)
      ? fieldErrorsRaw
          .map((entry) => ({
            field: typeof entry?.field === 'string' ? entry.field.trim() : '',
            message: typeof entry?.message === 'string' ? entry.message.trim() : '',
          }))
          .filter((entry) => entry.field.length > 0 && entry.message.length > 0)
      : [];
    if (fieldErrors.length > 0) {
      const fieldSummary = fieldErrors
        .slice(0, 4)
        .map((entry) => `${entry.field}: ${entry.message}`)
        .join(' | ');
      const detailPrefix = typeof detail === 'string' && detail.trim().length > 0 ? detail.trim() : 'Validation failed.';
      return new Error(`${detailPrefix} ${fieldSummary}`);
    }

    const message =
      typeof error.response?.data === 'string'
        ? error.response.data
        : (detail as string | undefined) ?? error.message;
    return new Error(message);
  }
  if (error instanceof Error) {
    return error;
  }
  return new Error('Unknown request error');
}

export class NipeApiClient {
  private readonly client: AxiosInstance;

  constructor(baseUrl: string = appEnv.apiBaseUrl) {
    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 30_000,
    });
  }

  get baseUrl() {
    return this.client.defaults.baseURL ?? appEnv.apiBaseUrl;
  }

  async getModeCatalog() {
    try {
      const response = await this.client.get('/api/modes');
      return modeCatalogSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async createProject(title: string, doNotStoreSourceText: boolean = false) {
    try {
      const response = await this.client.post('/api/projects', {
        title,
        do_not_store_source_text: doNotStoreSourceText,
      });
      return projectSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectLLMSettings(projectId: number): Promise<ProjectLLMSettingsResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/llm`);
      return projectLLMSettingsResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async updateProjectLLMSettings(
    projectId: number,
    payload: ProjectLLMSettingsRequestDto,
  ): Promise<ProjectLLMSettingsResponseDto> {
    const parsedPayload = projectLLMSettingsRequestSchema.parse(payload);
    try {
      const response = await this.client.put(`/api/projects/${projectId}/llm`, parsedPayload);
      return projectLLMSettingsResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async switchProjectMode(projectId: number, mode: string) {
    try {
      const response = await this.client.put(`/api/projects/${projectId}/mode`, { mode });
      return projectModeSwitchResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestTxt(projectId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/txt`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestChapterDirectory(projectId: number, files: File[]) {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/chapters-dir`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestMarkdown(projectId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/markdown`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestEpub(projectId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/epub`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async appendChapter(projectId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/append-chapter`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async importCharacters(projectId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await this.client.post(`/api/projects/${projectId}/characters/import`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return characterImportSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getCharacters(projectId: number) {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/characters`);
      return characterMapSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async saveCharacters(projectId: number, payload: CharacterMapUpdateDto): Promise<CharacterMapDto> {
    const parsedPayload = characterMapUpdateSchema.parse(payload);

    try {
      const response = await this.client.put(`/api/projects/${projectId}/characters`, parsedPayload);
      return characterMapSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getCharacterGenderComparison(
    projectId: number,
    includeOnlyConflicts: boolean = false,
  ): Promise<CharacterGenderComparisonResponseDto> {
    const response = await this.client.get(`/api/projects/${projectId}/characters/gender-comparison`, {
      params: includeOnlyConflicts ? { include_only_conflicts: true } : undefined,
    });

    try {
      return characterGenderComparisonResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async finalizeCharacterMap(projectId: number): Promise<CharacterMapFinalizeDto> {
    try {
      const response = await this.client.post(`/api/projects/${projectId}/characters/finalize`);
      return characterMapFinalizeSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async extractCharacters(projectId: number) {
    try {
      const response = await this.client.post(`/api/projects/${projectId}/characters/extract`);
      return characterExtractionSchema.parse(response.data) as CharacterExtractionDto;
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async scrapeCharacters(projectId: number, payload: CharacterScrapeRequestDto) {
    try {
      const parsedPayload = characterScrapeRequestSchema.parse(payload);
      const response = await this.client.post(`/api/projects/${projectId}/characters/scrape`, parsedPayload);
      return characterExtractionSchema.parse(response.data) as CharacterExtractionDto;
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async mergeCharacters(projectId: number, payload: CharacterCandidatesMergeRequestDto) {
    try {
      const parsedPayload = characterCandidatesMergeRequestSchema.parse(payload);
      const response = await this.client.post(
        `/api/projects/${projectId}/characters/merged-candidates`,
        parsedPayload,
      );
      return characterExtractionSchema.parse(response.data) as CharacterExtractionDto;
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async previewPronunciationDictionary(
    projectId: number,
    payload: PronunciationDictionaryPreviewRequestDto,
  ): Promise<PronunciationDictionaryPreviewResponseDto> {
    const parsedPayload = pronunciationDictionaryPreviewRequestSchema.parse(payload);
    try {
      const response = await this.client.post(
        `/api/projects/${projectId}/pronunciation-dictionary/preview`,
        parsedPayload,
      );
      return pronunciationDictionaryPreviewResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async saveVoices(projectId: number, payload: VoiceConfigDto) {
    try {
      const response = await this.client.put(`/api/projects/${projectId}/voices`, payload);
      return voiceConfigResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async runPipeline(projectId: number, payload: RunRequestDto) {
    const parsedPayload = runRequestSchema.parse(payload);

    try {
      const response = await this.client.post(`/api/projects/${projectId}/runs`, parsedPayload);
      return runResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getRunDetail(projectId: number, runId: number) {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/runs/${runId}`);
      return runDetailSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getRunConfigDiff(
    projectId: number,
    baseRunId: number,
    targetRunId: number,
  ): Promise<RunConfigDiffResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/runs/config-diff`, {
        params: {
          base_run_id: baseRunId,
          target_run_id: targetRunId,
        },
      });
      return runConfigDiffResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getExport(projectId: number, runId: number) {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/exports/${runId}.json`);
      return exportSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getTensionGraph(projectId: number, runId: number): Promise<TensionGraphResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/runs/${runId}/tension-graph`);
      return tensionGraphResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getCharacterAnalytics(projectId: number, runId: number): Promise<CharacterAnalyticsResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/runs/${runId}/character-analytics`);
      return characterAnalyticsResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getCharacterCooccurrenceGraph(projectId: number, runId: number): Promise<CharacterCooccurrenceGraphResponseDto> {
    try {
      const response = await this.client.get(
        `/api/projects/${projectId}/runs/${runId}/character-cooccurrence-graph`,
      );
      return characterCooccurrenceGraphResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getAudiobookPrepDashboard(projectId: number, runId: number): Promise<AudiobookPrepDashboardResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/runs/${runId}/audiobook-prep-dashboard`);
      return audiobookPrepDashboardResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }
}

export const nipeApiClient = new NipeApiClient();
