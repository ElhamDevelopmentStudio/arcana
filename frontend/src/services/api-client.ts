import axios, { AxiosError, type AxiosInstance } from 'axios';

import { appEnv } from '@/app/config/env';
import {
  characterImportSchema,
  characterMapSchema,
  characterMapUpdateSchema,
  exportSchema,
  ingestResponseSchema,
  modeCatalogSchema,
  projectSchema,
  projectModeSwitchResponseSchema,
  runDetailSchema,
  runRequestSchema,
  runResponseSchema,
  voiceConfigResponseSchema,
  type RunRequestDto,
  type VoiceConfigDto,
  type CharacterMapDto,
  type CharacterMapUpdateDto,
} from '@/app/schemas/api';

function normalizeHttpError(error: unknown): Error {
  if (error instanceof AxiosError) {
    const message =
      typeof error.response?.data === 'string'
        ? error.response.data
        : (error.response?.data?.detail as string | undefined) ?? error.message;
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

  async createProject(title: string) {
    try {
      const response = await this.client.post('/api/projects', { title });
      return projectSchema.parse(response.data);
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

  async getExport(projectId: number, runId: number) {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/exports/${runId}.json`);
      return exportSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }
}

export const nipeApiClient = new NipeApiClient();
