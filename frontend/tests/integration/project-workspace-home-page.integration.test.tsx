import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectWorkspaceHomePage } from '@/pages/projects/project-workspace-home-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectDetailQueryMock = vi.fn();
const useUpdateProjectMetadataMutationMock = vi.fn();
const useArchiveProjectMutationMock = vi.fn();
const useProjectAllowedActionsQueryMock = vi.fn();
const useProjectActivityTimelineQueryMock = vi.fn();
const projectDetailMutateMock = vi.fn();
const projectAllowedActionsMutateMock = vi.fn();
const projectActivityTimelineMutateMock = vi.fn();
const updateProjectMetadataTriggerMock = vi.fn();
const archiveProjectTriggerMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectDetailQuery: (...args: Parameters<typeof useProjectDetailQueryMock>) => useProjectDetailQueryMock(...args),
  useUpdateProjectMetadataMutation: (...args: Parameters<typeof useUpdateProjectMetadataMutationMock>) =>
    useUpdateProjectMetadataMutationMock(...args),
  useArchiveProjectMutation: (...args: Parameters<typeof useArchiveProjectMutationMock>) =>
    useArchiveProjectMutationMock(...args),
  useProjectAllowedActionsQuery: (...args: Parameters<typeof useProjectAllowedActionsQueryMock>) =>
    useProjectAllowedActionsQueryMock(...args),
  useProjectActivityTimelineQuery: (...args: Parameters<typeof useProjectActivityTimelineQueryMock>) =>
    useProjectActivityTimelineQueryMock(...args),
}));

function renderProjectWorkspaceHomePage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id',
        element: <ProjectWorkspaceHomePage />,
      },
      {
        path: '/projects/:project_id/overview',
        element: <div data-testid="project-overview-route">Overview route</div>,
      },
      {
        path: '/projects/:project_id/setup',
        element: <div data-testid="project-setup-route">Setup route</div>,
      },
      {
        path: '/projects/:project_id/runs',
        element: <div data-testid="project-runs-route">Runs route</div>,
      },
    ],
    { initialEntries: ['/projects/77'] },
  );

  render(<RouterProvider router={router} />);
}

describe('project workspace home page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectDetailQueryMock.mockReset();
    useUpdateProjectMetadataMutationMock.mockReset();
    useArchiveProjectMutationMock.mockReset();
    useProjectAllowedActionsQueryMock.mockReset();
    useProjectActivityTimelineQueryMock.mockReset();
    projectDetailMutateMock.mockReset();
    projectAllowedActionsMutateMock.mockReset();
    projectActivityTimelineMutateMock.mockReset();
    updateProjectMetadataTriggerMock.mockReset();
    archiveProjectTriggerMock.mockReset();
    useUpdateProjectMetadataMutationMock.mockReturnValue({
      isMutating: false,
      trigger: updateProjectMetadataTriggerMock,
    });
    useArchiveProjectMutationMock.mockReturnValue({
      isMutating: false,
      trigger: archiveProjectTriggerMock,
    });
    updateProjectMetadataTriggerMock.mockResolvedValue({
      project_id: 77,
      title: 'Shadow Slave Workspace Updated',
      description: 'Updated detail',
      tags: ['arc', 'research'],
      updated_at: '2026-02-27T00:15:00Z',
    });
    useProjectAllowedActionsQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectAllowedActionsMutateMock,
      data: {
        schema_version: '1.0',
        output_schema: 'project_actions',
        output_format: 'json',
        output_id: 'project-actions-77',
        output_name: 'Project Allowed Actions',
        generated_at: '2026-02-27T00:15:00Z',
        generated_by: 'project_actions_endpoint',
        project_id: 77,
        lifecycle_state: 'configured',
        last_run_status: null,
        next_required_action: 'run',
        allowed_actions: ['run', 'export', 'configure', 'archive'],
        blocked_reason: null,
        required_step: null,
      },
    });
    useProjectActivityTimelineQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectActivityTimelineMutateMock,
      data: {
        schema_version: '1.0',
        output_schema: 'project_activity_timeline_json',
        output_format: 'json',
        output_id: 'project-timeline-77-page-1',
        output_name: 'Project Activity Timeline',
        generated_at: '2026-02-27T00:15:00Z',
        generated_by: 'project_activity_timeline_endpoint',
        project_id: 77,
        total_items: 2,
        page: 1,
        page_size: 5,
        has_next_page: false,
        items: [
          {
            event_id: 2,
            event_type: 'manual_edit',
            actor: 'system',
            run_id: null,
            created_at: '2026-02-27T00:14:00Z',
            event_metadata: { updated_fields: ['title'] },
          },
          {
            event_id: 1,
            event_type: 'create_project',
            actor: 'system',
            run_id: null,
            created_at: '2026-02-27T00:10:00Z',
            event_metadata: {},
          },
        ],
      },
    });
  });

  it('renders loading state while project detail is pending', () => {
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: true,
      data: undefined,
      error: undefined,
      mutate: projectDetailMutateMock,
    });

    renderProjectWorkspaceHomePage();

    expect(screen.getByTestId('project-workspace-home-loading')).toBeInTheDocument();
  });

  it('renders retryable error state when project detail fails', async () => {
    const user = userEvent.setup();
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      data: undefined,
      error: new Error('project detail failed'),
      mutate: projectDetailMutateMock,
    });

    renderProjectWorkspaceHomePage();

    expect(screen.getByTestId('project-workspace-home-error')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry project detail' }));
    expect(projectDetailMutateMock).toHaveBeenCalledTimes(1);
  });

  it('renders project detail fields and route links on success', () => {
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectDetailMutateMock,
      data: {
        project_id: 77,
        title: 'Shadow Slave Workspace',
        description: 'workspace-home detail',
        tags: ['poc'],
        lifecycle_state: 'configured',
        last_run_status: null,
        next_required_action: 'run',
        allowed_actions: ['run', 'archive'],
        selected_mode: 'author',
        selected_modes: ['author'],
        llm_enabled: true,
        do_not_store_source_text: false,
        character_map_finalized: false,
        configuration_snapshot_id: null,
        ingestion_timestamp: null,
        last_export_at: null,
        created_at: '2026-02-27T00:00:00Z',
        updated_at: '2026-02-27T00:10:00Z',
      },
    });

    renderProjectWorkspaceHomePage();

    expect(screen.getByTestId('project-workspace-home-ready')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-home-title')).toHaveTextContent('Shadow Slave Workspace');
    expect(screen.getByTestId('project-workspace-home-id')).toHaveTextContent('Project ID: 77');
    expect(screen.getByTestId('project-workspace-home-lifecycle')).toHaveTextContent('Lifecycle: configured');
    expect(screen.getByTestId('project-workspace-home-next-action')).toHaveTextContent('Next action: run');
    expect(screen.getByTestId('project-workspace-home-mode')).toHaveTextContent('Mode: author');
    expect(screen.getByTestId('project-workspace-home-open-overview')).toHaveAttribute('href', '/projects/77/overview');
    expect(screen.getByTestId('project-workspace-home-open-setup')).toHaveAttribute('href', '/projects/77/setup');
    expect(screen.getByTestId('project-workspace-home-open-runs')).toHaveAttribute('href', '/projects/77/runs');
    expect(screen.getByTestId('project-metadata-title-input')).toHaveValue('Shadow Slave Workspace');
    expect(screen.getByTestId('project-metadata-description-input')).toHaveValue('workspace-home detail');
    expect(screen.getByTestId('project-metadata-tags-input')).toHaveValue('poc');
    expect(screen.getByTestId('project-command-panel')).toBeInTheDocument();
    expect(screen.getByTestId('project-command-panel-allowed-action-run')).toBeInTheDocument();
    expect(screen.getByTestId('project-command-panel-allowed-action-export')).toBeInTheDocument();
    expect(screen.getByTestId('project-command-panel-open-runs')).toHaveAttribute('href', '/projects/77/runs');
    expect(screen.getByTestId('project-command-panel-open-exports')).toHaveAttribute('href', '/projects/77/exports');
    expect(screen.getByTestId('project-command-panel-open-settings')).toHaveAttribute('href', '/projects/77/settings');
    expect(screen.getByTestId('project-command-panel-archive-button')).toBeInTheDocument();
    expect(screen.getByTestId('project-timeline-panel')).toBeInTheDocument();
    expect(screen.getByTestId('project-timeline-pagination-state')).toHaveTextContent('Page 1 / size 5 / total 2');
    expect(screen.getByTestId('project-timeline-item-2')).toHaveTextContent('manual_edit');
    expect(screen.getByTestId('project-timeline-item-1')).toHaveTextContent('create_project');
    expect(screen.getByTestId('project-timeline-prev-page')).toBeDisabled();
    expect(screen.getByTestId('project-timeline-next-page')).toBeDisabled();
  });

  it('renders blocked action state with reason and disabled commands', () => {
    useProjectAllowedActionsQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectAllowedActionsMutateMock,
      data: {
        schema_version: '1.0',
        output_schema: 'project_actions',
        output_format: 'json',
        output_id: 'project-actions-77',
        output_name: 'Project Allowed Actions',
        generated_at: '2026-02-27T00:15:00Z',
        generated_by: 'project_actions_endpoint',
        project_id: 77,
        lifecycle_state: 'archived',
        last_run_status: null,
        next_required_action: 'archived',
        allowed_actions: ['restore'],
        blocked_reason: 'Project is archived. Restore the project to continue workflow actions.',
        required_step: 'restore',
      },
    });
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectDetailMutateMock,
      data: {
        project_id: 77,
        title: 'Shadow Slave Workspace',
        description: 'workspace-home detail',
        tags: ['poc'],
        lifecycle_state: 'archived',
        last_run_status: null,
        next_required_action: 'archived',
        allowed_actions: ['restore'],
        selected_mode: 'author',
        selected_modes: ['author'],
        llm_enabled: true,
        do_not_store_source_text: false,
        character_map_finalized: false,
        configuration_snapshot_id: null,
        ingestion_timestamp: null,
        last_export_at: null,
        created_at: '2026-02-27T00:00:00Z',
        updated_at: '2026-02-27T00:10:00Z',
      },
    });

    renderProjectWorkspaceHomePage();

    expect(screen.getByTestId('project-command-panel-required-step')).toHaveTextContent('Required step: restore');
    expect(screen.getByTestId('project-command-panel-blocked-reason')).toHaveTextContent(
      'Project is archived. Restore the project to continue workflow actions.',
    );
    expect(screen.getByTestId('project-command-panel-open-runs-disabled')).toBeInTheDocument();
    expect(screen.getByTestId('project-command-panel-open-exports-disabled')).toBeInTheDocument();
    expect(screen.getByTestId('project-command-panel-archive-button-disabled')).toBeInTheDocument();
  });

  it('submits metadata edits through patch mutation', async () => {
    const user = userEvent.setup();
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectDetailMutateMock,
      data: {
        project_id: 77,
        title: 'Shadow Slave Workspace',
        description: 'workspace-home detail',
        tags: ['poc'],
        lifecycle_state: 'configured',
        last_run_status: null,
        next_required_action: 'run',
        allowed_actions: ['run', 'archive'],
        selected_mode: 'author',
        selected_modes: ['author'],
        llm_enabled: true,
        do_not_store_source_text: false,
        character_map_finalized: false,
        configuration_snapshot_id: null,
        ingestion_timestamp: null,
        last_export_at: null,
        created_at: '2026-02-27T00:00:00Z',
        updated_at: '2026-02-27T00:10:00Z',
      },
    });

    renderProjectWorkspaceHomePage();

    await user.clear(screen.getByTestId('project-metadata-title-input'));
    await user.type(screen.getByTestId('project-metadata-title-input'), 'Shadow Slave Workspace Updated');
    await user.clear(screen.getByTestId('project-metadata-description-input'));
    await user.type(screen.getByTestId('project-metadata-description-input'), 'Updated detail');
    await user.clear(screen.getByTestId('project-metadata-tags-input'));
    await user.type(screen.getByTestId('project-metadata-tags-input'), 'arc, research');
    await user.click(screen.getByTestId('project-metadata-save-button'));

    expect(updateProjectMetadataTriggerMock).toHaveBeenCalledTimes(1);
    expect(updateProjectMetadataTriggerMock).toHaveBeenCalledWith({
      title: 'Shadow Slave Workspace Updated',
      description: 'Updated detail',
      tags: ['arc', 'research'],
    });
    expect(projectDetailMutateMock).toHaveBeenCalledTimes(1);
  });

  it('submits archive command when archive action is allowed', async () => {
    const user = userEvent.setup();
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectDetailMutateMock,
      data: {
        project_id: 77,
        title: 'Shadow Slave Workspace',
        description: 'workspace-home detail',
        tags: ['poc'],
        lifecycle_state: 'configured',
        last_run_status: 'completed',
        next_required_action: 'export',
        allowed_actions: ['run', 'export', 'archive'],
        selected_mode: 'author',
        selected_modes: ['author'],
        llm_enabled: true,
        do_not_store_source_text: false,
        character_map_finalized: false,
        configuration_snapshot_id: null,
        ingestion_timestamp: null,
        last_export_at: null,
        created_at: '2026-02-27T00:00:00Z',
        updated_at: '2026-02-27T00:10:00Z',
      },
    });
    archiveProjectTriggerMock.mockResolvedValue({
      project_id: 77,
      action: 'archive',
      previous_lifecycle_state: 'configured',
      lifecycle_state: 'archived',
      next_required_action: 'archived',
      allowed_actions: ['restore'],
    });

    renderProjectWorkspaceHomePage();

    await user.click(screen.getByTestId('project-command-panel-archive-button'));

    expect(archiveProjectTriggerMock).toHaveBeenCalledTimes(1);
    expect(projectAllowedActionsMutateMock).toHaveBeenCalledTimes(1);
    expect(projectDetailMutateMock).toHaveBeenCalledTimes(1);
    expect(projectActivityTimelineMutateMock).toHaveBeenCalledTimes(1);
  });

  it('requests next timeline page when next pagination action is available', async () => {
    const user = userEvent.setup();
    useProjectActivityTimelineQueryMock.mockImplementation(
      (_projectId: number | null, params: { page: number; page_size: number }) => ({
        isLoading: false,
        error: undefined,
        mutate: projectActivityTimelineMutateMock,
        data: {
          schema_version: '1.0',
          output_schema: 'project_activity_timeline_json',
          output_format: 'json',
          output_id: `project-timeline-77-page-${params.page}`,
          output_name: 'Project Activity Timeline',
          generated_at: '2026-02-27T00:15:00Z',
          generated_by: 'project_activity_timeline_endpoint',
          project_id: 77,
          total_items: 8,
          page: params.page,
          page_size: params.page_size,
          has_next_page: params.page < 2,
          items: [
            {
              event_id: 20 - params.page,
              event_type: 'run_complete',
              actor: 'system',
              run_id: 900,
              created_at: '2026-02-27T00:20:00Z',
              event_metadata: {},
            },
          ],
        },
      }),
    );
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectDetailMutateMock,
      data: {
        project_id: 77,
        title: 'Shadow Slave Workspace',
        description: 'workspace-home detail',
        tags: ['poc'],
        lifecycle_state: 'configured',
        last_run_status: 'completed',
        next_required_action: 'export',
        allowed_actions: ['run', 'export', 'archive'],
        selected_mode: 'author',
        selected_modes: ['author'],
        llm_enabled: true,
        do_not_store_source_text: false,
        character_map_finalized: false,
        configuration_snapshot_id: null,
        ingestion_timestamp: null,
        last_export_at: null,
        created_at: '2026-02-27T00:00:00Z',
        updated_at: '2026-02-27T00:10:00Z',
      },
    });

    renderProjectWorkspaceHomePage();

    expect(screen.getByTestId('project-timeline-pagination-state')).toHaveTextContent('Page 1 / size 5 / total 8');
    await user.click(screen.getByTestId('project-timeline-next-page'));
    expect(screen.getByTestId('project-timeline-pagination-state')).toHaveTextContent('Page 2 / size 5 / total 8');
    expect(screen.getByTestId('project-timeline-prev-page')).toBeEnabled();
    expect(screen.getByTestId('project-timeline-next-page')).toBeDisabled();
  });
});
