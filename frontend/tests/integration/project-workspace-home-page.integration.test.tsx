import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectWorkspaceHomePage } from '@/pages/projects/project-workspace-home-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectDetailQueryMock = vi.fn();
const useUpdateProjectMetadataMutationMock = vi.fn();
const projectDetailMutateMock = vi.fn();
const updateProjectMetadataTriggerMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectDetailQuery: (...args: Parameters<typeof useProjectDetailQueryMock>) => useProjectDetailQueryMock(...args),
  useUpdateProjectMetadataMutation: (...args: Parameters<typeof useUpdateProjectMetadataMutationMock>) =>
    useUpdateProjectMetadataMutationMock(...args),
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
    projectDetailMutateMock.mockReset();
    updateProjectMetadataTriggerMock.mockReset();
    useUpdateProjectMetadataMutationMock.mockReturnValue({
      isMutating: false,
      trigger: updateProjectMetadataTriggerMock,
    });
    updateProjectMetadataTriggerMock.mockResolvedValue({
      project_id: 77,
      title: 'Shadow Slave Workspace Updated',
      description: 'Updated detail',
      tags: ['arc', 'research'],
      updated_at: '2026-02-27T00:15:00Z',
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
});
