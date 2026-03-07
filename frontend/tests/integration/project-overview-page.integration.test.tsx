import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectOverviewPage } from '@/pages/projects/project-overview-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectDetailQueryMock = vi.fn();
const useProjectWorkspaceSummaryQueryMock = vi.fn();
const projectDetailMutateMock = vi.fn();
const workspaceSummaryMutateMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectDetailQuery: (...args: Parameters<typeof useProjectDetailQueryMock>) => useProjectDetailQueryMock(...args),
  useProjectWorkspaceSummaryQuery: (...args: Parameters<typeof useProjectWorkspaceSummaryQueryMock>) =>
    useProjectWorkspaceSummaryQueryMock(...args),
}));

function renderProjectOverviewPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/overview',
        element: <ProjectOverviewPage />,
      },
      {
        path: '/projects/:project_id/setup',
        element: <div data-testid="project-setup-route">Project setup route</div>,
      },
    ],
    { initialEntries: ['/projects/77/overview'] },
  );

  render(<RouterProvider router={router} />);
  return router;
}

describe('project overview page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectDetailQueryMock.mockReset();
    useProjectWorkspaceSummaryQueryMock.mockReset();
    projectDetailMutateMock.mockReset();
    workspaceSummaryMutateMock.mockReset();
  });

  it('renders loading state while project detail is pending', () => {
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: true,
      data: undefined,
      error: undefined,
      mutate: projectDetailMutateMock,
    });
    useProjectWorkspaceSummaryQueryMock.mockReturnValue({
      isLoading: true,
      data: undefined,
      error: undefined,
      mutate: workspaceSummaryMutateMock,
    });

    renderProjectOverviewPage();

    expect(screen.getByTestId('project-overview-loading')).toBeInTheDocument();
  });

  it('renders retryable project detail error state', async () => {
    const user = userEvent.setup();
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      data: undefined,
      error: new Error('project detail failed'),
      mutate: projectDetailMutateMock,
    });
    useProjectWorkspaceSummaryQueryMock.mockReturnValue({
      isLoading: false,
      data: undefined,
      error: undefined,
      mutate: workspaceSummaryMutateMock,
    });

    renderProjectOverviewPage();

    expect(screen.getByTestId('project-overview-project-detail-error')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry project detail' }));
    expect(projectDetailMutateMock).toHaveBeenCalledTimes(1);
  });

  it('renders project detail and workspace summary contracts on success', () => {
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectDetailMutateMock,
      data: {
        project_id: 77,
        title: 'Shadow Slave PoC',
        description: 'Narrative processing baseline',
        tags: ['poc', 'author'],
        lifecycle_state: 'configured',
        last_run_status: null,
        next_required_action: 'run',
        allowed_actions: ['run', 'select_mode'],
        selected_mode: 'author',
        selected_modes: ['author'],
        llm_enabled: true,
        do_not_store_source_text: false,
        character_map_finalized: false,
        configuration_snapshot_id: null,
        ingestion_timestamp: '2026-02-27T00:00:00Z',
        last_export_at: null,
        created_at: '2026-02-27T00:00:00Z',
        updated_at: '2026-02-27T00:10:00Z',
      },
    });
    useProjectWorkspaceSummaryQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: workspaceSummaryMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'configured',
        last_run_status: null,
        next_required_action: 'run',
        is_setup_complete: false,
        chapters_count: 12,
        characters_count: 9,
        voice_mappings_count: 5,
        runs_total_count: 1,
        runs_completed_count: 0,
        runs_failed_count: 0,
        last_export_at: null,
      },
    });

    renderProjectOverviewPage();

    expect(screen.getByTestId('project-overview-ready')).toBeInTheDocument();
    expect(screen.getByTestId('project-overview-detail-card')).toBeInTheDocument();
    expect(screen.getByText('Shadow Slave PoC')).toBeInTheDocument();
    expect(screen.getByText('Chapters: 12')).toBeInTheDocument();
    expect(screen.getByText('Voice mappings: 5')).toBeInTheDocument();
  });

  it('navigates to setup via overview action CTA', async () => {
    const user = userEvent.setup();
    useProjectDetailQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: projectDetailMutateMock,
      data: {
        project_id: 77,
        title: 'Shadow Slave PoC',
        description: null,
        tags: [],
        lifecycle_state: 'configured',
        last_run_status: null,
        next_required_action: 'run',
        allowed_actions: ['run'],
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
    useProjectWorkspaceSummaryQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: workspaceSummaryMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'configured',
        last_run_status: null,
        next_required_action: 'run',
        is_setup_complete: false,
        chapters_count: 12,
        characters_count: 9,
        voice_mappings_count: 5,
        runs_total_count: 1,
        runs_completed_count: 0,
        runs_failed_count: 0,
        last_export_at: null,
      },
    });

    const router = renderProjectOverviewPage();
    await user.click(screen.getByTestId('project-overview-open-setup'));

    expect(await screen.findByTestId('project-setup-route')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/77/setup');
  });
});
