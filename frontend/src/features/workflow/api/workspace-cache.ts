import type { Key } from 'swr';

import type {
  ProjectActivityTimelineRequestDto,
  ProjectControlPanelProjectListRequestDto,
} from '@/app/schemas/api';

export const workspaceKeys = {
  health: ['health'] as const,
  modeCatalog: ['mode-catalog'] as const,
  llmProviders: ['llm-providers'] as const,
  projectControlPanelSummary: ['project-control-panel-summary'] as const,
  projectControlPanelProjectList: (params: ProjectControlPanelProjectListRequestDto) =>
    ['project-control-panel-project-list', params] as const,
  projectAllowedActions: (projectId: number) => ['project-allowed-actions', projectId] as const,
  projectActivityTimeline: (projectId: number, params: ProjectActivityTimelineRequestDto) =>
    ['project-activity-timeline', projectId, params] as const,
  projectDetail: (projectId: number) => ['project-detail', projectId] as const,
  projectAccessList: (projectId: number) => ['project-access-list', projectId] as const,
  projectLLMSettings: (projectId: number) => ['project-llm-settings', projectId] as const,
  projectWorkspaceSummary: (projectId: number) => ['project-workspace-summary', projectId] as const,
  projectSetupStatus: (projectId: number) => ['project-setup-status', projectId] as const,
  runDetail: (projectId: number, runId: number) => ['run-detail', projectId, runId] as const,
  runConfigPreset: (projectId: number, runId: number) => ['run-config-preset', projectId, runId] as const,
  runConfigDiff: (projectId: number, baseRunId: number, targetRunId: number) =>
    ['run-config-diff', projectId, baseRunId, targetRunId] as const,
  exportPayload: (projectId: number, runId: number) => ['export-payload', projectId, runId] as const,
  tensionGraph: (projectId: number, runId: number) => ['tension-graph', projectId, runId] as const,
  characterAnalytics: (projectId: number, runId: number) => ['character-analytics', projectId, runId] as const,
  characterCooccurrenceGraph: (projectId: number, runId: number) => [
    'character-cooccurrence-graph',
    projectId,
    runId,
  ] as const,
  audiobookPrepDashboard: (projectId: number, runId: number) => ['audiobook-prep-dashboard', projectId, runId] as const,
  pipelineStageDurationsDashboard: (projectId: number, runId: number) =>
    ['pipeline-stage-durations-dashboard', projectId, runId] as const,
  characterMap: (projectId: number) => ['character-map', projectId] as const,
  characterGenderComparison: (projectId: number) => ['character-gender-comparison', projectId] as const,
};

const runScopedKeyPrefixes = new Set<string>([
  'run-detail',
  'run-config-preset',
  'run-config-diff',
  'export-payload',
  'tension-graph',
  'character-analytics',
  'character-cooccurrence-graph',
  'audiobook-prep-dashboard',
  'pipeline-stage-durations-dashboard',
]);

function isProjectScopedRunKey(key: unknown, projectId: number): boolean {
  return (
    Array.isArray(key) &&
    key.length > 1 &&
    typeof key[0] === 'string' &&
    key[1] === projectId &&
    runScopedKeyPrefixes.has(key[0])
  );
}

export const workspaceKeyMatchers = {
  projectControlPanelProjectList: (key: unknown) =>
    Array.isArray(key) && key.length > 0 && key[0] === 'project-control-panel-project-list',
  projectActivityTimeline: (projectId: number) => (key: unknown) =>
    Array.isArray(key) && key.length > 1 && key[0] === 'project-activity-timeline' && key[1] === projectId,
  projectScopedRunData: (projectId: number) => (key: unknown) => isProjectScopedRunKey(key, projectId),
};

export type WorkspaceMutationTarget = Key | ((key: unknown) => boolean);

type WorkspaceMutationContext = {
  projectId?: number | null;
};

export type WorkspaceMutationName =
  | 'create_project'
  | 'create_project_draft'
  | 'update_project_metadata'
  | 'update_project_llm_settings'
  | 'update_llm_provider_status'
  | 'archive_project'
  | 'restore_project'
  | 'switch_mode'
  | 'run_pipeline'
  | 'cancel_run';

type WorkspaceMutationInvalidationResolver = (
  context: WorkspaceMutationContext,
) => readonly WorkspaceMutationTarget[];

export const workspaceMutationInvalidationMap: Record<
  WorkspaceMutationName,
  WorkspaceMutationInvalidationResolver
> = {
  create_project: () => [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList],
  create_project_draft: () => [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList],
  update_project_metadata: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeyMatchers.projectActivityTimeline(projectId),
      workspaceKeys.projectDetail(projectId),
      workspaceKeys.projectWorkspaceSummary(projectId),
      workspaceKeys.projectSetupStatus(projectId),
    ];
  },
  update_project_llm_settings: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeys.projectDetail(projectId),
      workspaceKeys.projectLLMSettings(projectId),
      workspaceKeys.projectWorkspaceSummary(projectId),
      workspaceKeys.projectSetupStatus(projectId),
      workspaceKeyMatchers.projectActivityTimeline(projectId),
    ];
  },
  update_llm_provider_status: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.llmProviders, workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.llmProviders,
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeys.projectDetail(projectId),
      workspaceKeys.projectLLMSettings(projectId),
      workspaceKeys.projectWorkspaceSummary(projectId),
      workspaceKeys.projectSetupStatus(projectId),
      workspaceKeyMatchers.projectActivityTimeline(projectId),
    ];
  },
  archive_project: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeys.projectAllowedActions(projectId),
      workspaceKeyMatchers.projectActivityTimeline(projectId),
      workspaceKeys.projectDetail(projectId),
      workspaceKeys.projectWorkspaceSummary(projectId),
      workspaceKeys.projectSetupStatus(projectId),
    ];
  },
  restore_project: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeys.projectAllowedActions(projectId),
      workspaceKeyMatchers.projectActivityTimeline(projectId),
      workspaceKeys.projectDetail(projectId),
      workspaceKeys.projectWorkspaceSummary(projectId),
      workspaceKeys.projectSetupStatus(projectId),
    ];
  },
  switch_mode: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeyMatchers.projectScopedRunData(projectId),
    ];
  },
  run_pipeline: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeyMatchers.projectScopedRunData(projectId),
    ];
  },
  cancel_run: ({ projectId }) => {
    if (projectId === null || projectId === undefined) {
      return [workspaceKeys.projectControlPanelSummary, workspaceKeyMatchers.projectControlPanelProjectList];
    }
    return [
      workspaceKeys.projectControlPanelSummary,
      workspaceKeyMatchers.projectControlPanelProjectList,
      workspaceKeyMatchers.projectScopedRunData(projectId),
    ];
  },
};

export function resolveWorkspaceMutationInvalidationTargets(
  mutation: WorkspaceMutationName,
  context: WorkspaceMutationContext = {},
): readonly WorkspaceMutationTarget[] {
  return workspaceMutationInvalidationMap[mutation](context);
}
