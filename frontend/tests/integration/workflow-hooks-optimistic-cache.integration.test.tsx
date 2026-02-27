import { useMemo } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SWRConfig } from 'swr';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useArchiveProjectMutation,
  useProjectAllowedActionsQuery,
  useProjectControlPanelProjectListQuery,
  useProjectDetailQuery,
  useProjectWorkspaceSummaryQuery,
} from '@/features/workflow/api/workflow-hooks';
import { nipeApiClient } from '@/services/api-client';

function ArchiveOptimisticRollbackHarness() {
  const listParams = useMemo(() => ({ page: 1, page_size: 20 }), []);
  const projectDetailQuery = useProjectDetailQuery(77);
  const projectAllowedActionsQuery = useProjectAllowedActionsQuery(77);
  const projectWorkspaceSummaryQuery = useProjectWorkspaceSummaryQuery(77);
  const projectListQuery = useProjectControlPanelProjectListQuery(true, listParams);
  const archiveProjectMutation = useArchiveProjectMutation(77);

  return (
    <div>
      <p data-testid="optimistic-detail-lifecycle">{projectDetailQuery.data?.lifecycle_state ?? 'none'}</p>
      <p data-testid="optimistic-actions-lifecycle">{projectAllowedActionsQuery.data?.lifecycle_state ?? 'none'}</p>
      <p data-testid="optimistic-workspace-lifecycle">{projectWorkspaceSummaryQuery.data?.lifecycle_state ?? 'none'}</p>
      <p data-testid="optimistic-dashboard-list-status">{projectListQuery.data?.items[0]?.status ?? 'none'}</p>

      <button
        type="button"
        onClick={() => {
          void archiveProjectMutation.trigger().catch(() => undefined);
        }}
      >
        Trigger optimistic archive
      </button>
    </div>
  );
}

describe('workflow hooks optimistic cross-route cache updates', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('optimistically updates project caches and rolls back when archive fails', async () => {
    const user = userEvent.setup();

    vi.spyOn(nipeApiClient, 'getProjectDetail').mockResolvedValue({
      schema_version: '1.0',
      output_schema: 'project_detail_json',
      output_format: 'json',
      output_id: 'project-77-detail',
      output_name: 'Project Detail',
      generated_at: '2026-02-27T00:00:00Z',
      generated_by: 'project_detail_endpoint',
      project_id: 77,
      title: 'Optimistic Cache Project',
      description: null,
      tags: [],
      lifecycle_state: 'configured',
      last_run_status: null,
      next_required_action: 'run',
      allowed_actions: ['run', 'export', 'archive'],
      selected_mode: 'author',
      selected_modes: ['author'],
      llm_enabled: true,
      do_not_store_source_text: false,
      configuration_snapshot_id: null,
      voice_config_json: null,
      llm_provider_config_json: null,
      default_narrator_voice: null,
      default_male_voice: null,
      default_female_voice: null,
      default_neutral_voice: null,
      default_unknown_voice: null,
      ingestion_log_json: null,
      ingestion_timestamp: null,
      character_map_finalized: false,
      last_export_at: null,
      created_at: '2026-02-27T00:00:00Z',
      updated_at: '2026-02-27T00:00:00Z',
    });
    vi.spyOn(nipeApiClient, 'getProjectAllowedActions').mockResolvedValue({
      schema_version: '1.0',
      output_schema: 'project_actions',
      output_format: 'json',
      output_id: 'project-actions-77',
      output_name: 'Project Allowed Actions',
      generated_at: '2026-02-27T00:00:00Z',
      generated_by: 'project_actions_endpoint',
      project_id: 77,
      lifecycle_state: 'configured',
      last_run_status: null,
      next_required_action: 'run',
      allowed_actions: ['run', 'export', 'archive'],
      blocked_reason: null,
      required_step: null,
    });
    vi.spyOn(nipeApiClient, 'getProjectWorkspaceSummary').mockResolvedValue({
      schema_version: '1.0',
      output_schema: 'project_workspace_summary_json',
      output_format: 'json',
      output_id: 'project-workspace-summary-77',
      output_name: 'Project Workspace Summary',
      generated_at: '2026-02-27T00:00:00Z',
      generated_by: 'project_workspace_summary_endpoint',
      project_id: 77,
      lifecycle_state: 'configured',
      last_run_status: null,
      next_required_action: 'run',
      is_setup_complete: true,
      chapters_count: 1,
      characters_count: 3,
      voice_mappings_count: 4,
      runs_total_count: 2,
      runs_completed_count: 2,
      runs_failed_count: 0,
      last_export_at: null,
    });
    vi.spyOn(nipeApiClient, 'getProjectControlPanelProjectList').mockResolvedValue({
      schema_version: '1.0',
      output_schema: 'project_control_panel_project_list_json',
      output_format: 'json',
      output_id: 'dashboard-project-list-1',
      output_name: 'Project Control Panel Project List',
      generated_at: '2026-02-27T00:00:00Z',
      generated_by: 'project_control_panel_project_list_endpoint',
      total_items: 1,
      page: 1,
      page_size: 20,
      has_next_page: false,
      items: [
        {
          project_id: 77,
          status: 'configured',
          selected_mode: 'author',
          last_run_status: null,
          updated_at: '2026-02-27T00:00:00Z',
          next_required_action: 'run',
        },
      ],
    });

    let rejectArchive: ((error: Error) => void) | null = null;
    const archiveProjectSpy = vi.spyOn(nipeApiClient, 'archiveProject').mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectArchive = reject as (error: Error) => void;
        }),
    );

    render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <ArchiveOptimisticRollbackHarness />
      </SWRConfig>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('optimistic-detail-lifecycle')).toHaveTextContent('configured');
    });

    await user.click(screen.getByRole('button', { name: 'Trigger optimistic archive' }));

    await waitFor(() => {
      expect(screen.getByTestId('optimistic-detail-lifecycle')).toHaveTextContent('archived');
      expect(screen.getByTestId('optimistic-actions-lifecycle')).toHaveTextContent('archived');
      expect(screen.getByTestId('optimistic-workspace-lifecycle')).toHaveTextContent('archived');
      expect(screen.getByTestId('optimistic-dashboard-list-status')).toHaveTextContent('archived');
    });

    rejectArchive?.(new Error('archive failed'));

    await waitFor(() => {
      expect(screen.getByTestId('optimistic-detail-lifecycle')).toHaveTextContent('configured');
      expect(screen.getByTestId('optimistic-actions-lifecycle')).toHaveTextContent('configured');
      expect(screen.getByTestId('optimistic-workspace-lifecycle')).toHaveTextContent('configured');
      expect(screen.getByTestId('optimistic-dashboard-list-status')).toHaveTextContent('configured');
    });
    expect(archiveProjectSpy).toHaveBeenCalledTimes(1);
  });
});
