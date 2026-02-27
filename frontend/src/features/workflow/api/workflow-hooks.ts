import useSWR, { useSWRConfig } from 'swr';
import useSWRMutation from 'swr/mutation';

import { runRequestSchema, type RunRequestDto } from '@/app/schemas/api';
import { nipeApiClient } from '@/services/api-client';
import type { VoiceConfigDto } from '@/app/schemas/api';
import type { CharacterMapUpdateDto } from '@/app/schemas/api';
import type { CharacterScrapeRequestDto } from '@/app/schemas/api';
import type { CharacterCandidatesMergeRequestDto } from '@/app/schemas/api';
import type { PronunciationDictionaryPreviewRequestDto } from '@/app/schemas/api';
import { useMutationEventBus } from '@/features/workflow/events/mutation-event-bus';
import {
  resolveWorkspaceMutationInvalidationTargets,
  workspaceKeys,
  type WorkspaceMutationName,
} from './workspace-cache';

export { workspaceKeys } from './workspace-cache';

function useMutationEventPublisher() {
  return useMutationEventBus((state) => state.publish);
}

function useWorkspaceMutationInvalidator() {
  const { mutate } = useSWRConfig();
  return async (
    mutation: WorkspaceMutationName,
    context: {
      projectId?: number | null;
    } = {},
  ) => {
    const targets = resolveWorkspaceMutationInvalidationTargets(mutation, context);
    await Promise.all(targets.map((target) => mutate(target as never)));
  };
}

export function useModeCatalogQuery(enabled: boolean) {
  return useSWR(enabled ? workspaceKeys.modeCatalog : null, async () => nipeApiClient.getModeCatalog());
}

export function useHealthQuery(enabled: boolean) {
  return useSWR(enabled ? workspaceKeys.health : null, async () => nipeApiClient.getHealth());
}

export function useLLMProvidersQuery(enabled: boolean) {
  return useSWR(enabled ? workspaceKeys.llmProviders : null, async () => nipeApiClient.getLLMProviderStatuses());
}

export function useProjectControlPanelSummaryQuery(enabled: boolean) {
  return useSWR(
    enabled ? workspaceKeys.projectControlPanelSummary : null,
    async () => nipeApiClient.getProjectControlPanelSummary(),
  );
}

export function useProjectControlPanelProjectListQuery(
  enabled: boolean,
  params: {
    page: number;
    page_size: number;
    status?: string;
    selected_mode?: string;
    last_run_status?: string;
    next_required_action?: string;
  },
) {
  return useSWR(
    enabled ? workspaceKeys.projectControlPanelProjectList(params) : null,
    async ([, currentParams]) => nipeApiClient.getProjectControlPanelProjectList(currentParams),
  );
}

export function useProjectActivityTimelineQuery(
  projectId: number | null,
  params: {
    page: number;
    page_size: number;
  },
) {
  return useSWR(
    projectId !== null ? workspaceKeys.projectActivityTimeline(projectId, params) : null,
    async ([, currentProjectId, currentParams]) => nipeApiClient.getProjectActivityTimeline(currentProjectId, currentParams),
  );
}

export function useProjectAllowedActionsQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.projectAllowedActions(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getProjectAllowedActions(currentProjectId),
  );
}

export function useProjectDetailQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.projectDetail(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getProjectDetail(currentProjectId),
  );
}

export function useProjectAccessListQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.projectAccessList(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getProjectAccessList(currentProjectId),
  );
}

export function useGrantProjectAccessMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    projectId !== null ? ['grant-project-access', projectId] : null,
    async (
      _,
      {
        arg,
      }: {
        arg: { principal_id: string; principal_type: 'user' | 'service' | 'system'; role: 'owner' | 'editor' | 'viewer' };
      },
    ) => {
      if (projectId === null) {
        throw new Error('Project must exist before granting access.');
      }
      return nipeApiClient.grantProjectAccess(projectId, arg);
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('grant_project_access', { projectId });
      },
    },
  );
}

export function useProjectLLMSettingsQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.projectLLMSettings(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getProjectLLMSettings(currentProjectId),
  );
}

export function useProjectWorkspaceSummaryQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.projectWorkspaceSummary(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getProjectWorkspaceSummary(currentProjectId),
  );
}

export function useProjectSetupStatusQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.projectSetupStatus(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getProjectSetupStatus(currentProjectId),
  );
}

export function useRunDetailQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.runDetail(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) => nipeApiClient.getRunDetail(currentProjectId, currentRunId),
  );
}

export function useRunConfigPresetMutation(projectId: number | null, runId: number | null) {
  return useSWRMutation(
    projectId !== null && runId !== null ? workspaceKeys.runConfigPreset(projectId, runId) : null,
    async () => {
      if (projectId === null || runId === null) {
        throw new Error('Project and run are required before exporting a config preset.');
      }
      return nipeApiClient.getRunConfigPreset(projectId, runId);
    },
  );
}

export function useRunConfigDiffQuery(
  projectId: number | null,
  baseRunId: number | null,
  targetRunId: number | null,
) {
  return useSWR(
    projectId !== null && baseRunId !== null && targetRunId !== null
      ? workspaceKeys.runConfigDiff(projectId, baseRunId, targetRunId)
      : null,
    async ([, currentProjectId, currentBaseRunId, currentTargetRunId]) =>
      nipeApiClient.getRunConfigDiff(currentProjectId, currentBaseRunId, currentTargetRunId),
  );
}

export function useExportPayloadQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.exportPayload(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) => nipeApiClient.getExport(currentProjectId, currentRunId),
  );
}

export function useTensionGraphQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.tensionGraph(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) => nipeApiClient.getTensionGraph(currentProjectId, currentRunId),
  );
}

export function useCharacterAnalyticsQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.characterAnalytics(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) => nipeApiClient.getCharacterAnalytics(currentProjectId, currentRunId),
  );
}

export function useCharacterCooccurrenceGraphQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.characterCooccurrenceGraph(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) =>
      nipeApiClient.getCharacterCooccurrenceGraph(currentProjectId, currentRunId),
  );
}

export function useAudiobookPrepDashboardQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.audiobookPrepDashboard(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) => nipeApiClient.getAudiobookPrepDashboard(currentProjectId, currentRunId),
  );
}

export function usePipelineStageDurationsDashboardQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.pipelineStageDurationsDashboard(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) =>
      nipeApiClient.getPipelineStageDurationsDashboard(currentProjectId, currentRunId),
  );
}

export function useCreateProjectMutation() {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    ['create-project'],
    async (_, { arg }: { arg: { title: string; do_not_store_source_text: boolean } }) =>
      nipeApiClient.createProject(arg.title, arg.do_not_store_source_text),
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('create_project');
      },
    },
  );
}

export function useCreateProjectDraftMutation() {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  const publishMutationEvent = useMutationEventPublisher();
  return useSWRMutation(
    ['create-project-draft'],
    async (_, { arg }: { arg: { title: string; do_not_store_source_text: boolean } }) => {
      try {
        const project = await nipeApiClient.createProjectDraft(arg.title, arg.do_not_store_source_text);
        publishMutationEvent({
          level: 'success',
          title: 'Draft project created',
          message: `Project #${project.id} is ready for ingestion.`,
        });
        return project;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to create draft project.';
        publishMutationEvent({
          level: 'error',
          title: 'Draft project creation failed',
          message,
          recoveryLabel: 'Reload app',
          onRecovery: () => window.location.reload(),
        });
        throw error;
      }
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('create_project_draft');
      },
    },
  );
}

export function useUpdateProjectMetadataMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    projectId !== null ? ['update-project-metadata', projectId] : null,
    async (
      _,
      {
        arg,
      }: {
        arg: { title?: string; description?: string | null; tags?: string[] };
      },
    ) => {
      if (projectId === null) {
        throw new Error('Project must exist before metadata update.');
      }
      return nipeApiClient.updateProjectMetadata(projectId, arg);
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('update_project_metadata', { projectId });
      },
    },
  );
}

export function useUpdateProjectLLMSettingsMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    projectId !== null ? ['update-project-llm-settings', projectId] : null,
    async (_, { arg }: { arg: { llm_enabled: boolean } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before updating LLM settings.');
      }
      return nipeApiClient.updateProjectLLMSettings(projectId, arg);
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('update_project_llm_settings', { projectId });
      },
    },
  );
}

export function useUpdateLLMProviderStatusMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    ['update-llm-provider-status'],
    async (_, { arg }: { arg: { provider_name: string; enabled: boolean } }) =>
      nipeApiClient.updateLLMProviderStatus(arg.provider_name, { enabled: arg.enabled }),
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('update_llm_provider_status', { projectId });
      },
    },
  );
}

export function useArchiveProjectMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    projectId !== null ? ['archive-project', projectId] : null,
    async () => {
      if (projectId === null) {
        throw new Error('Project must exist before archive.');
      }
      return nipeApiClient.archiveProject(projectId);
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('archive_project', { projectId });
      },
    },
  );
}

export function useRestoreProjectMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    projectId !== null ? ['restore-project', projectId] : null,
    async () => {
      if (projectId === null) {
        throw new Error('Project must exist before restore.');
      }
      return nipeApiClient.restoreProject(projectId);
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('restore_project', { projectId });
      },
    },
  );
}

export function useSwitchModeMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    projectId !== null ? ['switch-mode', projectId] : null,
    async (_, { arg }: { arg: { mode: string } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before mode switching.');
      }
      return nipeApiClient.switchProjectMode(projectId, arg.mode);
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('switch_mode', { projectId });
      },
    },
  );
}

export function useIngestTxtMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['ingest-txt', projectId] : null,
    async (_, { arg }: { arg: { file: File } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before ingestion.');
      }
      return nipeApiClient.ingestTxt(projectId, arg.file);
    },
  );
}

export function useAttachInitialIngestionSourceMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['attach-initial-ingestion-source', projectId] : null,
    async (_, { arg }: { arg: { source: 'txt' | 'markdown' | 'epub' | 'chapters-dir'; source_filename?: string } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before attaching ingestion source.');
      }
      return nipeApiClient.attachInitialIngestionSource(projectId, arg);
    },
  );
}

export function useIngestChapterDirectoryMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['ingest-chapters-dir', projectId] : null,
    async (_, { arg }: { arg: { files: File[] } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before ingestion.');
      }
      return nipeApiClient.ingestChapterDirectory(projectId, arg.files);
    },
  );
}

export function useIngestMarkdownMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['ingest-markdown', projectId] : null,
    async (_, { arg }: { arg: { file: File } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before ingestion.');
      }
      return nipeApiClient.ingestMarkdown(projectId, arg.file);
    },
  );
}

export function useIngestEpubMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['ingest-epub', projectId] : null,
    async (_, { arg }: { arg: { file: File } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before ingestion.');
      }
      return nipeApiClient.ingestEpub(projectId, arg.file);
    },
  );
}

export function useAppendChapterMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['append-chapter', projectId] : null,
    async (_, { arg }: { arg: { file: File } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before append ingestion.');
      }
      return nipeApiClient.appendChapter(projectId, arg.file);
    },
  );
}

export function useImportCharactersMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['import-characters', projectId] : null,
    async (_, { arg }: { arg: { file: File } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before importing characters.');
      }
      return nipeApiClient.importCharacters(projectId, arg.file);
    },
  );
}

export function useCharacterMapQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.characterMap(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getCharacters(currentProjectId),
  );
}

export function useCharacterGenderComparisonQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? workspaceKeys.characterGenderComparison(projectId) : null,
    async ([, currentProjectId]) => nipeApiClient.getCharacterGenderComparison(currentProjectId),
  );
}

export function useCharacterAliasCollisionsQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? ['character-alias-collisions', projectId] : null,
    async ([, currentProjectId]) => nipeApiClient.getCharacterAliasCollisions(currentProjectId),
  );
}

export function useArtifactPronunciationDictionaryQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? ['pronunciation-dictionary-artifacts', projectId] : null,
    async ([, currentProjectId]) => nipeApiClient.getArtifactPronunciationDictionary(currentProjectId),
  );
}

export function useInventedPronunciationDictionaryQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? ['pronunciation-dictionary-invented', projectId] : null,
    async ([, currentProjectId]) => nipeApiClient.getInventedPronunciationDictionary(currentProjectId),
  );
}

export function useGlobalPronunciationDictionaryQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? ['pronunciation-dictionary-global', projectId] : null,
    async ([, currentProjectId]) => nipeApiClient.getGlobalPronunciationDictionary(currentProjectId),
  );
}

export function usePlacePronunciationDictionaryQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? ['pronunciation-dictionary-places', projectId] : null,
    async ([, currentProjectId]) => nipeApiClient.getPlacePronunciationDictionary(currentProjectId),
  );
}

export function useCharacterPronunciationDictionaryQuery(
  projectId: number | null,
  characterName: string | null,
) {
  return useSWR(
    projectId !== null && characterName !== null
      ? ['pronunciation-dictionary-character', projectId, characterName]
      : null,
    async ([, currentProjectId, currentCharacterName]) =>
      nipeApiClient.getCharacterPronunciationDictionary(currentProjectId, currentCharacterName),
  );
}

export function useSaveCharacterMapMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['save-characters', projectId] : null,
    async (_, { arg }: { arg: CharacterMapUpdateDto }) => {
      if (projectId === null) {
        throw new Error('Project must exist before saving character map.');
      }
      return nipeApiClient.saveCharacters(projectId, arg);
    },
  );
}

export function useFinalizeCharacterMapMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['finalize-characters', projectId] : null,
    async () => {
      if (projectId === null) {
        throw new Error('Project must exist before finalizing character map.');
      }
      return nipeApiClient.finalizeCharacterMap(projectId);
    },
  );
}

export function useAutoExtractCharactersMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['extract-characters', projectId] : null,
    async () => {
      if (projectId === null) {
        throw new Error('Project must exist before extracting characters.');
      }
      return nipeApiClient.extractCharacters(projectId);
    },
  );
}

export function useScrapeCharactersMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['scrape-characters', projectId] : null,
    async (_, { arg }: { arg: CharacterScrapeRequestDto }) => {
      if (projectId === null) {
        throw new Error('Project must exist before scraping characters.');
      }
      return nipeApiClient.scrapeCharacters(projectId, arg);
    },
  );
}

export function useMergeCharactersMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['merge-characters', projectId] : null,
    async (_, { arg }: { arg: CharacterCandidatesMergeRequestDto }) => {
      if (projectId === null) {
        throw new Error('Project must exist before merging character candidates.');
      }
      return nipeApiClient.mergeCharacters(projectId, arg);
    },
  );
}

export function useInferCharacterGendersMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['infer-character-genders', projectId] : null,
    async () => {
      if (projectId === null) {
        throw new Error('Project must exist before inferring character genders.');
      }
      return nipeApiClient.inferCharacterGenders(projectId);
    },
  );
}

export function useLookupCharacterAliasMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['lookup-character-alias', projectId] : null,
    async (_, { arg }: { arg: { alias: string } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before alias lookup.');
      }
      return nipeApiClient.lookupCharacterAlias(projectId, arg);
    },
  );
}

export function useSaveArtifactPronunciationDictionaryMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['save-pronunciation-dictionary-artifacts', projectId] : null,
    async (
      _,
      {
        arg,
      }: {
        arg: { entries: Array<{ term: string; verbalized_form: string; source: string; confidence: number }> };
      },
    ) => {
      if (projectId === null) {
        throw new Error('Project must exist before saving artifact pronunciation dictionary.');
      }
      return nipeApiClient.updateArtifactPronunciationDictionary(projectId, arg);
    },
  );
}

export function useSaveInventedPronunciationDictionaryMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['save-pronunciation-dictionary-invented', projectId] : null,
    async (
      _,
      {
        arg,
      }: {
        arg: { entries: Array<{ term: string; verbalized_form: string; source: string; confidence: number }> };
      },
    ) => {
      if (projectId === null) {
        throw new Error('Project must exist before saving invented pronunciation dictionary.');
      }
      return nipeApiClient.updateInventedPronunciationDictionary(projectId, arg);
    },
  );
}

export function useSaveGlobalPronunciationDictionaryMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['save-pronunciation-dictionary-global', projectId] : null,
    async (
      _,
      {
        arg,
      }: {
        arg: { entries: Array<{ term: string; verbalized_form: string; source: string; confidence: number }> };
      },
    ) => {
      if (projectId === null) {
        throw new Error('Project must exist before saving global pronunciation dictionary.');
      }
      return nipeApiClient.updateGlobalPronunciationDictionary(projectId, arg);
    },
  );
}

export function useSavePlacePronunciationDictionaryMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['save-pronunciation-dictionary-places', projectId] : null,
    async (
      _,
      {
        arg,
      }: {
        arg: { entries: Array<{ term: string; verbalized_form: string; source: string; confidence: number }> };
      },
    ) => {
      if (projectId === null) {
        throw new Error('Project must exist before saving place pronunciation dictionary.');
      }
      return nipeApiClient.updatePlacePronunciationDictionary(projectId, arg);
    },
  );
}

export function useSaveCharacterPronunciationDictionaryMutation(
  projectId: number | null,
  characterName: string | null,
) {
  return useSWRMutation(
    projectId !== null && characterName !== null
      ? ['save-pronunciation-dictionary-character', projectId, characterName]
      : null,
    async (
      _,
      {
        arg,
      }: {
        arg: { entries: Array<{ term: string; verbalized_form: string; source: string; confidence: number }> };
      },
    ) => {
      if (projectId === null) {
        throw new Error('Project must exist before saving character pronunciation dictionary.');
      }
      if (characterName === null) {
        throw new Error('Character name is required before saving character pronunciation dictionary.');
      }
      return nipeApiClient.updateCharacterPronunciationDictionary(projectId, characterName, arg);
    },
  );
}

export function usePronunciationPreviewMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['preview-pronunciation-dictionary', projectId] : null,
    async (_, { arg }: { arg: PronunciationDictionaryPreviewRequestDto }) => {
      if (projectId === null) {
        throw new Error('Project must exist before previewing pronunciation dictionary changes.');
      }
      return nipeApiClient.previewPronunciationDictionary(projectId, arg);
    },
  );
}

export function useSaveVoicesMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['save-voices', projectId] : null,
    async (_, { arg }: { arg: VoiceConfigDto }) => {
      if (projectId === null) {
        throw new Error('Project must exist before saving voice configuration.');
      }
      return nipeApiClient.saveVoices(projectId, arg);
    },
  );
}

export function useRunPipelineMutation(projectId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  return useSWRMutation(
    projectId !== null ? ['run-pipeline', projectId] : null,
    async (_, { arg }: { arg: RunRequestDto }) => {
      if (projectId === null) {
        throw new Error('Project must exist before running the pipeline.');
      }
      return nipeApiClient.runPipeline(projectId, runRequestSchema.parse(arg));
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('run_pipeline', { projectId });
      },
    },
  );
}

export function useCancelRunMutation(projectId: number | null, runId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  const publishMutationEvent = useMutationEventPublisher();
  return useSWRMutation(
    projectId !== null && runId !== null ? ['cancel-run', projectId, runId] : null,
    async () => {
      if (projectId === null || runId === null) {
        throw new Error('Project and run are required before cancelling a run.');
      }
      try {
        const run = await nipeApiClient.cancelRun(projectId, runId);
        publishMutationEvent({
          level: 'success',
          title: 'Run cancelled',
          message: `Run #${run.run_id} was cancelled.`,
        });
        return run;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to cancel run.';
        publishMutationEvent({
          level: 'error',
          title: 'Run cancellation failed',
          message,
          recoveryLabel: 'Reload app',
          onRecovery: () => window.location.reload(),
        });
        throw error;
      }
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('cancel_run', { projectId });
      },
    },
  );
}

export function useRerunRunMutation(projectId: number | null, runId: number | null) {
  const invalidateWorkspaceMutation = useWorkspaceMutationInvalidator();
  const publishMutationEvent = useMutationEventPublisher();
  return useSWRMutation(
    projectId !== null && runId !== null ? ['rerun-run', projectId, runId] : null,
    async () => {
      if (projectId === null || runId === null) {
        throw new Error('Project and run are required before rerunning a run.');
      }
      try {
        const run = await nipeApiClient.rerunRun(projectId, runId);
        publishMutationEvent({
          level: 'success',
          title: 'Run rerun started',
          message: `Rerun #${run.run_id} completed.`,
        });
        return run;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to rerun run.';
        publishMutationEvent({
          level: 'error',
          title: 'Rerun failed',
          message,
          recoveryLabel: 'Reload app',
          onRecovery: () => window.location.reload(),
        });
        throw error;
      }
    },
    {
      onSuccess: async () => {
        await invalidateWorkspaceMutation('rerun_run', { projectId });
      },
    },
  );
}
