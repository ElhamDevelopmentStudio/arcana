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

export function useProjectAllowedActionsQuery(projectId: number | null) {
  return useSWR(
    projectId !== null ? ['project-allowed-actions', projectId] : null,
    async ([, currentProjectId]) => nipeApiClient.getProjectAllowedActions(currentProjectId),
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
