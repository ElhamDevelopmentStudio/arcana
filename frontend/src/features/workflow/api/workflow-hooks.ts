import useSWR from 'swr';
import useSWRMutation from 'swr/mutation';

import { runRequestSchema, type RunRequestDto } from '@/app/schemas/api';
import { nipeApiClient } from '@/services/api-client';
import type { VoiceConfigDto } from '@/app/schemas/api';

export const workspaceKeys = {
  modeCatalog: ['mode-catalog'] as const,
  runDetail: (projectId: number, runId: number) => ['run-detail', projectId, runId] as const,
  exportPayload: (projectId: number, runId: number) => ['export-payload', projectId, runId] as const,
};

export function useModeCatalogQuery(enabled: boolean) {
  return useSWR(enabled ? workspaceKeys.modeCatalog : null, async () => nipeApiClient.getModeCatalog());
}

export function useRunDetailQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.runDetail(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) => nipeApiClient.getRunDetail(currentProjectId, currentRunId),
  );
}

export function useExportPayloadQuery(projectId: number | null, runId: number | null) {
  return useSWR(
    projectId !== null && runId !== null ? workspaceKeys.exportPayload(projectId, runId) : null,
    async ([, currentProjectId, currentRunId]) => nipeApiClient.getExport(currentProjectId, currentRunId),
  );
}

export function useCreateProjectMutation() {
  return useSWRMutation(
    ['create-project'],
    async (_, { arg }: { arg: { title: string } }) => nipeApiClient.createProject(arg.title),
  );
}

export function useSwitchModeMutation(projectId: number | null) {
  return useSWRMutation(
    projectId !== null ? ['switch-mode', projectId] : null,
    async (_, { arg }: { arg: { mode: string } }) => {
      if (projectId === null) {
        throw new Error('Project must exist before mode switching.');
      }
      return nipeApiClient.switchProjectMode(projectId, arg.mode);
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
  return useSWRMutation(
    projectId !== null ? ['run-pipeline', projectId] : null,
    async (_, { arg }: { arg: RunRequestDto }) => {
      if (projectId === null) {
        throw new Error('Project must exist before running the pipeline.');
      }
      return nipeApiClient.runPipeline(projectId, runRequestSchema.parse(arg));
    },
  );
}
