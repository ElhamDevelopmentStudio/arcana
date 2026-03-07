import { describe, expect, it } from 'vitest';

import {
  resolveWorkspaceMutationInvalidationTargets,
  workspaceKeyMatchers,
  workspaceKeys,
} from '@/features/workflow/api/workspace-cache';

describe('workspace key factory', () => {
  it('builds deterministic project/run/dashboard keys', () => {
    expect(workspaceKeys.health).toEqual(['health']);
    expect(workspaceKeys.projectControlPanelSummary).toEqual(['project-control-panel-summary']);
    expect(workspaceKeys.llmProviders).toEqual(['llm-providers']);
    expect(workspaceKeys.runDetail(11, 42)).toEqual(['run-detail', 11, 42]);
    expect(workspaceKeys.projectAccessList(11)).toEqual(['project-access-list', 11]);
    expect(workspaceKeys.projectLLMSettings(11)).toEqual(['project-llm-settings', 11]);
    expect(workspaceKeys.projectControlPanelProjectList({ page: 1, page_size: 20 })).toEqual([
      'project-control-panel-project-list',
      { page: 1, page_size: 20 },
    ]);
  });

  it('matches dashboard project-list key families', () => {
    const matchingKey = workspaceKeys.projectControlPanelProjectList({
      page: 2,
      page_size: 10,
      status: 'running',
    });
    expect(workspaceKeyMatchers.projectControlPanelProjectList(matchingKey)).toBe(true);
    expect(workspaceKeyMatchers.projectControlPanelProjectList(['run-detail', 3, 7])).toBe(false);
  });
});

describe('workspace mutation invalidation map', () => {
  it('invalidates dashboard summary and list after project creation', () => {
    const targets = resolveWorkspaceMutationInvalidationTargets('create_project');
    expect(targets[0]).toEqual(workspaceKeys.projectControlPanelSummary);
    expect(typeof targets[1]).toBe('function');
  });

  it('adds project-scoped run-data invalidation for run mutations', () => {
    const targets = resolveWorkspaceMutationInvalidationTargets('run_pipeline', { projectId: 21 });
    const projectRunMatcher = targets[7];

    expect(typeof projectRunMatcher).toBe('function');
    expect(targets).toContainEqual(workspaceKeys.projectDetail(21));
    expect(targets).toContainEqual(workspaceKeys.projectAllowedActions(21));
    expect(targets).toContainEqual(workspaceKeys.projectWorkspaceSummary(21));
    expect(targets).toContainEqual(workspaceKeys.projectSetupStatus(21));
    expect((projectRunMatcher as (key: unknown) => boolean)(['run-detail', 21, 9])).toBe(true);
    expect((projectRunMatcher as (key: unknown) => boolean)(['run-detail', 99, 9])).toBe(false);
    expect((projectRunMatcher as (key: unknown) => boolean)(['project-control-panel-summary'])).toBe(false);
  });

  it('adds project-scoped run-data invalidation for recover and rerun mutations', () => {
    const rerunTargets = resolveWorkspaceMutationInvalidationTargets('rerun_run', { projectId: 21 });
    const recoverTargets = resolveWorkspaceMutationInvalidationTargets('recover_run', { projectId: 21 });

    const rerunMatcher = rerunTargets[7];
    const recoverMatcher = recoverTargets[7];

    expect(typeof rerunMatcher).toBe('function');
    expect(typeof recoverMatcher).toBe('function');
    expect(rerunTargets).toContainEqual(workspaceKeys.projectAllowedActions(21));
    expect(recoverTargets).toContainEqual(workspaceKeys.projectAllowedActions(21));
    expect((rerunMatcher as (key: unknown) => boolean)(['run-detail', 21, 9])).toBe(true);
    expect((recoverMatcher as (key: unknown) => boolean)(['run-detail', 21, 9])).toBe(true);
  });

  it('invalidates project llm settings key on llm settings mutation', () => {
    const targets = resolveWorkspaceMutationInvalidationTargets('update_project_llm_settings', { projectId: 21 });

    expect(targets).toContainEqual(workspaceKeys.projectLLMSettings(21));
    expect(targets).toContainEqual(workspaceKeys.projectDetail(21));
    expect(targets).toContainEqual(workspaceKeys.projectWorkspaceSummary(21));
  });

  it('invalidates provider and project scoped keys on provider status mutation', () => {
    const targets = resolveWorkspaceMutationInvalidationTargets('update_llm_provider_status', { projectId: 21 });

    expect(targets).toContainEqual(workspaceKeys.llmProviders);
    expect(targets).toContainEqual(workspaceKeys.projectDetail(21));
    expect(targets).toContainEqual(workspaceKeys.projectLLMSettings(21));
    expect(targets).toContainEqual(workspaceKeys.projectWorkspaceSummary(21));
  });

  it('invalidates project access list on access grant mutation', () => {
    const targets = resolveWorkspaceMutationInvalidationTargets('grant_project_access', { projectId: 21 });

    expect(targets).toContainEqual(workspaceKeys.projectAccessList(21));
    expect(targets).toContainEqual(workspaceKeys.projectDetail(21));
    expect(targets).toContainEqual(workspaceKeys.projectWorkspaceSummary(21));
  });
});
