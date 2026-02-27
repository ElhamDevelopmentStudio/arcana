import axios, { type AxiosInstance } from 'axios';

import { appEnv } from '@/app/config/env';
import { normalizeHttpError } from '@/services/api-error';
import {
  characterImportSchema,
  characterAnalyticsResponseSchema,
  characterCooccurrenceGraphResponseSchema,
  characterGenderComparisonRequestSchema,
  characterMapSchema,
  characterMapUpdateSchema,
  characterMapFinalizeSchema,
  characterCandidatesMergeRequestSchema,
  characterAliasLookupRequestSchema,
  characterAliasLookupResponseSchema,
  characterAliasCollisionResponseSchema,
  pronunciationDictionaryUpdateRequestSchema,
  pronunciationDictionaryResponseSchema,
  characterScrapeRequestSchema,
  pronunciationDictionaryPreviewRequestSchema,
  pronunciationDictionaryPreviewResponseSchema,
  audiobookPrepDashboardResponseSchema,
  pipelineStageDurationsDashboardResponseSchema,
  exportSchema,
  tensionGraphResponseSchema,
  ingestResponseSchema,
  modeCatalogSchema,
  healthSchema,
  projectControlPanelSummaryResponseSchema,
  projectControlPanelProjectListRequestSchema,
  projectControlPanelProjectListResponseSchema,
  projectActivityTimelineRequestSchema,
  projectActivityTimelineResponseSchema,
  projectAllowedActionsResponseSchema,
  projectLifecycleStateChangeResponseSchema,
  projectDetailResponseSchema,
  projectSetupStatusResponseSchema,
  projectWorkspaceSummaryResponseSchema,
  projectIngestionSourceAttachRequestSchema,
  projectIngestionSourceAttachResponseSchema,
  projectAccessGrantRequestSchema,
  projectAccessGrantResponseSchema,
  projectAccessListResponseSchema,
  projectCreateRequestSchema,
  projectMetadataUpdateRequestSchema,
  projectMetadataUpdateResponseSchema,
  projectSchema,
  projectLLMSettingsRequestSchema,
  projectLLMSettingsResponseSchema,
  llmProviderStatusSchema,
  llmProviderStatusUpdateRequestSchema,
  llmProvidersResponseSchema,
  projectModeSwitchRequestSchema,
  projectModeSwitchResponseSchema,
  runDetailSchema,
  runConfigDiffRequestSchema,
  runConfigDiffResponseSchema,
  runConfigPresetResponseSchema,
  runRequestSchema,
  runResponseSchema,
  characterGenderComparisonResponseSchema,
  singleFileUploadRequestSchema,
  multiFileUploadRequestSchema,
  voiceConfigSchema,
  voiceConfigResponseSchema,
  type RunRequestDto,
  type RunConfigDiffResponseDto,
  type RunConfigPresetResponseDto,
  type ProjectLLMSettingsRequestDto,
  type ProjectLLMSettingsResponseDto,
  type LLMProviderStatusDto,
  type LLMProviderStatusUpdateRequestDto,
  type LLMProvidersResponseDto,
  type HealthDto,
  type ProjectControlPanelSummaryResponseDto,
  type ProjectControlPanelProjectListRequestDto,
  type ProjectControlPanelProjectListResponseDto,
  type ProjectActivityTimelineRequestDto,
  type ProjectActivityTimelineResponseDto,
  type ProjectAllowedActionsResponseDto,
  type ProjectLifecycleStateChangeResponseDto,
  type ProjectDetailResponseDto,
  type ProjectSetupStatusResponseDto,
  type ProjectWorkspaceSummaryResponseDto,
  type ProjectIngestionSourceAttachRequestDto,
  type ProjectIngestionSourceAttachResponseDto,
  type ProjectAccessGrantRequestDto,
  type ProjectAccessGrantResponseDto,
  type ProjectAccessListResponseDto,
  type ProjectMetadataUpdateRequestDto,
  type ProjectMetadataUpdateResponseDto,
  type VoiceConfigDto,
  type CharacterMapDto,
  type CharacterMapUpdateDto,
  type CharacterMapFinalizeDto,
  type CharacterScrapeRequestDto,
  type CharacterCandidatesMergeRequestDto,
  type CharacterAliasLookupRequestDto,
  type CharacterAliasLookupResponseDto,
  type CharacterAliasCollisionResponseDto,
  type PronunciationDictionaryUpdateRequestDto,
  type PronunciationDictionaryResponseDto,
  type CharacterAnalyticsResponseDto,
  type CharacterCooccurrenceGraphResponseDto,
  type CharacterExtractionDto,
  type CharacterGenderComparisonResponseDto,
  type PronunciationDictionaryPreviewRequestDto,
  type PronunciationDictionaryPreviewResponseDto,
  type AudiobookPrepDashboardResponseDto,
  type PipelineStageDurationsDashboardResponseDto,
  type TensionGraphResponseDto,
  characterExtractionSchema,
} from '@/app/schemas/api';

export class NipeApiClient {
  private readonly client: AxiosInstance;
  private static readonly ingestRequestTimeoutMs = 5 * 60_000;

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

  async getHealth(): Promise<HealthDto> {
    try {
      const response = await this.client.get('/health');
      return healthSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async createProject(title: string, doNotStoreSourceText: boolean = false) {
    const parsedPayload = projectCreateRequestSchema.parse({
      title,
      do_not_store_source_text: doNotStoreSourceText,
    });
    try {
      const response = await this.client.post('/api/projects', parsedPayload);
      return projectSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async createProjectDraft(title: string, doNotStoreSourceText: boolean = false) {
    const parsedPayload = projectCreateRequestSchema.parse({
      title,
      do_not_store_source_text: doNotStoreSourceText,
    });
    try {
      const response = await this.client.post('/api/projects/drafts', parsedPayload);
      return projectSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async updateProjectMetadata(
    projectId: number,
    payload: ProjectMetadataUpdateRequestDto,
  ): Promise<ProjectMetadataUpdateResponseDto> {
    const parsedPayload = projectMetadataUpdateRequestSchema.parse(payload);
    try {
      const response = await this.client.patch(`/api/projects/${projectId}/metadata`, parsedPayload);
      return projectMetadataUpdateResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectControlPanelSummary(): Promise<ProjectControlPanelSummaryResponseDto> {
    try {
      const response = await this.client.get('/api/dashboard/project-control-panel/summary');
      return projectControlPanelSummaryResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectControlPanelProjectList(
    params?: ProjectControlPanelProjectListRequestDto,
  ): Promise<ProjectControlPanelProjectListResponseDto> {
    const parsedParams = projectControlPanelProjectListRequestSchema.parse(params ?? {});
    const hasParams = Object.keys(parsedParams).length > 0;
    try {
      const response = await this.client.get('/api/dashboard/project-control-panel/projects', {
        params: hasParams ? parsedParams : undefined,
      });
      return projectControlPanelProjectListResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectActivityTimeline(
    projectId: number,
    params?: ProjectActivityTimelineRequestDto,
  ): Promise<ProjectActivityTimelineResponseDto> {
    const parsedParams = projectActivityTimelineRequestSchema.parse(params ?? {});
    const hasParams = Object.keys(parsedParams).length > 0;
    try {
      const response = await this.client.get(`/api/projects/${projectId}/timeline`, {
        params: hasParams ? parsedParams : undefined,
      });
      return projectActivityTimelineResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectAllowedActions(projectId: number): Promise<ProjectAllowedActionsResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/actions`);
      return projectAllowedActionsResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async archiveProject(projectId: number): Promise<ProjectLifecycleStateChangeResponseDto> {
    try {
      const response = await this.client.post(`/api/projects/${projectId}/archive`);
      return projectLifecycleStateChangeResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async restoreProject(projectId: number): Promise<ProjectLifecycleStateChangeResponseDto> {
    try {
      const response = await this.client.post(`/api/projects/${projectId}/restore`);
      return projectLifecycleStateChangeResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectDetail(projectId: number): Promise<ProjectDetailResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}`);
      return projectDetailResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectWorkspaceSummary(projectId: number): Promise<ProjectWorkspaceSummaryResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/workspace-summary`);
      return projectWorkspaceSummaryResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectSetupStatus(projectId: number): Promise<ProjectSetupStatusResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/setup-status`);
      return projectSetupStatusResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async attachInitialIngestionSource(
    projectId: number,
    payload: ProjectIngestionSourceAttachRequestDto,
  ): Promise<ProjectIngestionSourceAttachResponseDto> {
    const parsedPayload = projectIngestionSourceAttachRequestSchema.parse(payload);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/source`, parsedPayload);
      return projectIngestionSourceAttachResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getProjectAccessList(projectId: number): Promise<ProjectAccessListResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/access`);
      return projectAccessListResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async grantProjectAccess(
    projectId: number,
    payload: ProjectAccessGrantRequestDto,
  ): Promise<ProjectAccessGrantResponseDto> {
    const parsedPayload = projectAccessGrantRequestSchema.parse(payload);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/access`, parsedPayload);
      return projectAccessGrantResponseSchema.parse(response.data);
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

  async getLLMProviderStatuses(): Promise<LLMProvidersResponseDto> {
    try {
      const response = await this.client.get('/api/llm/providers');
      return llmProvidersResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async updateLLMProviderStatus(
    providerName: string,
    payload: LLMProviderStatusUpdateRequestDto,
  ): Promise<LLMProviderStatusDto> {
    const parsedPayload = llmProviderStatusUpdateRequestSchema.parse(payload);
    try {
      const response = await this.client.put(`/api/llm/providers/${providerName}`, parsedPayload);
      return llmProviderStatusSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async switchProjectMode(projectId: number, mode: string) {
    const parsedPayload = projectModeSwitchRequestSchema.parse({ mode });
    try {
      const response = await this.client.put(`/api/projects/${projectId}/mode`, parsedPayload);
      return projectModeSwitchResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestTxt(projectId: number, file: File) {
    const parsedPayload = singleFileUploadRequestSchema.parse({ file });
    const formData = new FormData();
    formData.append('file', parsedPayload.file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/txt`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: NipeApiClient.ingestRequestTimeoutMs,
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestChapterDirectory(projectId: number, files: File[]) {
    const parsedPayload = multiFileUploadRequestSchema.parse({ files });
    const formData = new FormData();
    for (const file of parsedPayload.files) {
      formData.append('files', file);
    }
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/chapters-dir`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: NipeApiClient.ingestRequestTimeoutMs,
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestMarkdown(projectId: number, file: File) {
    const parsedPayload = singleFileUploadRequestSchema.parse({ file });
    const formData = new FormData();
    formData.append('file', parsedPayload.file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/markdown`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: NipeApiClient.ingestRequestTimeoutMs,
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async ingestEpub(projectId: number, file: File) {
    const parsedPayload = singleFileUploadRequestSchema.parse({ file });
    const formData = new FormData();
    formData.append('file', parsedPayload.file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/epub`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: NipeApiClient.ingestRequestTimeoutMs,
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async appendChapter(projectId: number, file: File) {
    const parsedPayload = singleFileUploadRequestSchema.parse({ file });
    const formData = new FormData();
    formData.append('file', parsedPayload.file);
    try {
      const response = await this.client.post(`/api/projects/${projectId}/ingest/append-chapter`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: NipeApiClient.ingestRequestTimeoutMs,
      });
      return ingestResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async importCharacters(projectId: number, file: File) {
    const parsedPayload = singleFileUploadRequestSchema.parse({ file });
    const formData = new FormData();
    formData.append('file', parsedPayload.file);

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
    const parsedParams = characterGenderComparisonRequestSchema.parse({
      include_only_conflicts: includeOnlyConflicts,
    });
    const response = await this.client.get(`/api/projects/${projectId}/characters/gender-comparison`, {
      params: parsedParams.include_only_conflicts ? parsedParams : undefined,
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

  async lookupCharacterAlias(
    projectId: number,
    payload: CharacterAliasLookupRequestDto,
  ): Promise<CharacterAliasLookupResponseDto> {
    try {
      const parsedPayload = characterAliasLookupRequestSchema.parse(payload);
      const response = await this.client.post(`/api/projects/${projectId}/characters/lookup-alias`, parsedPayload);
      return characterAliasLookupResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getCharacterAliasCollisions(projectId: number): Promise<CharacterAliasCollisionResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/characters/alias-collisions`);
      return characterAliasCollisionResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getArtifactPronunciationDictionary(projectId: number): Promise<PronunciationDictionaryResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/pronunciation-dictionary/artifacts`);
      return pronunciationDictionaryResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async updateArtifactPronunciationDictionary(
    projectId: number,
    payload: PronunciationDictionaryUpdateRequestDto,
  ): Promise<PronunciationDictionaryResponseDto> {
    try {
      const parsedPayload = pronunciationDictionaryUpdateRequestSchema.parse(payload);
      const response = await this.client.put(
        `/api/projects/${projectId}/pronunciation-dictionary/artifacts`,
        parsedPayload,
      );
      return pronunciationDictionaryResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getInventedPronunciationDictionary(projectId: number): Promise<PronunciationDictionaryResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/pronunciation-dictionary/invented`);
      return pronunciationDictionaryResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async updateInventedPronunciationDictionary(
    projectId: number,
    payload: PronunciationDictionaryUpdateRequestDto,
  ): Promise<PronunciationDictionaryResponseDto> {
    try {
      const parsedPayload = pronunciationDictionaryUpdateRequestSchema.parse(payload);
      const response = await this.client.put(
        `/api/projects/${projectId}/pronunciation-dictionary/invented`,
        parsedPayload,
      );
      return pronunciationDictionaryResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async inferCharacterGenders(projectId: number): Promise<CharacterMapDto> {
    try {
      const response = await this.client.post(`/api/projects/${projectId}/characters/infer`);
      return characterMapSchema.parse(response.data);
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
    const parsedPayload = voiceConfigSchema.parse(payload);
    try {
      const response = await this.client.put(`/api/projects/${projectId}/voices`, parsedPayload);
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

  async cancelRun(projectId: number, runId: number) {
    try {
      const response = await this.client.post(`/api/projects/${projectId}/runs/${runId}/cancel`);
      return runResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getRunConfigDiff(
    projectId: number,
    baseRunId: number,
    targetRunId: number,
  ): Promise<RunConfigDiffResponseDto> {
    const parsedParams = runConfigDiffRequestSchema.parse({
      base_run_id: baseRunId,
      target_run_id: targetRunId,
    });
    try {
      const response = await this.client.get(`/api/projects/${projectId}/runs/config-diff`, {
        params: parsedParams,
      });
      return runConfigDiffResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }

  async getRunConfigPreset(projectId: number, runId: number): Promise<RunConfigPresetResponseDto> {
    try {
      const response = await this.client.get(`/api/projects/${projectId}/runs/${runId}/config-preset`);
      return runConfigPresetResponseSchema.parse(response.data);
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

  async getPipelineStageDurationsDashboard(
    projectId: number,
    runId: number,
  ): Promise<PipelineStageDurationsDashboardResponseDto> {
    try {
      const response = await this.client.get(
        `/api/projects/${projectId}/runs/${runId}/pipeline-stage-durations-dashboard`,
      );
      return pipelineStageDurationsDashboardResponseSchema.parse(response.data);
    } catch (error) {
      throw normalizeHttpError(error);
    }
  }
}

export const nipeApiClient = new NipeApiClient();
