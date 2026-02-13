import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useUiRouteStateStore } from '@/app/state/ui-route-state-store';
import { DashboardPage } from '@/pages/dashboard/dashboard-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectControlPanelProjectListQueryMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectControlPanelSummaryQuery: () => ({
    data: {
      total_projects: 1,
      active_run_count: 0,
      recent_failure_count: 0,
    },
  }),
  useProjectControlPanelProjectListQuery: (...args: Parameters<typeof useProjectControlPanelProjectListQueryMock>) =>
    useProjectControlPanelProjectListQueryMock(...args),
}));

function renderDashboard(initialEntry: string = '/dashboard') {
  const router = createMemoryRouter(
    [
      {
        path: '/dashboard',
        element: <DashboardPage />,
      },
      {
        path: '/projects/:project_id/mode',
        element: <div data-testid="project-mode-route">Mode route</div>,
      },
      {
        path: '/projects/:project_id/run-monitor',
        element: <div data-testid="project-run-monitor-route">Run monitor route</div>,
      },
    ],
    {
      initialEntries: [initialEntry],
    },
  );

  render(<RouterProvider router={router} />);
}

describe('dashboard route/query state persistence', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectControlPanelProjectListQueryMock.mockReset();
    useProjectControlPanelProjectListQueryMock.mockReturnValue({
      data: {
        items: [
          {
            project_id: 101,
            status: 'ingested',
            selected_mode: 'audiobook',
            last_run_status: null,
            updated_at: '2026-02-27T00:00:00Z',
            next_required_action: 'select_mode',
          },
        ],
      },
    });
  });

  it('reuses persisted dashboard query state when route has no query params', async () => {
    useUiRouteStateStore.setState({
      dashboardListQuery: {
        page: 3,
        page_size: 25,
        status: 'running',
        selected_mode: 'author',
        last_run_status: 'failed',
        next_required_action: 'export',
      },
    });

    renderDashboard();

    await waitFor(() => {
      expect(useProjectControlPanelProjectListQueryMock).toHaveBeenCalled();
    });

    const lastCall = useProjectControlPanelProjectListQueryMock.mock.calls.at(-1);
    expect(lastCall?.[0]).toBe(true);
    expect(lastCall?.[1]).toMatchObject({
      page: 3,
      page_size: 25,
      status: 'running',
      selected_mode: 'author',
      last_run_status: 'failed',
      next_required_action: 'export',
    });
  });

  it('hydrates dashboard query state from URL params on reload', async () => {
    renderDashboard(
      '/dashboard?page=2&page_size=10&status=running&selected_mode=author&last_run_status=failed&next_required_action=export',
    );

    await waitFor(() => {
      expect(useProjectControlPanelProjectListQueryMock).toHaveBeenCalled();
    });

    const lastCall = useProjectControlPanelProjectListQueryMock.mock.calls.at(-1);
    expect(lastCall?.[1]).toMatchObject({
      page: 2,
      page_size: 10,
      status: 'running',
      selected_mode: 'author',
      last_run_status: 'failed',
      next_required_action: 'export',
    });
  });

  it('opens last visited project route when persisted', async () => {
    const user = userEvent.setup();
    useUiRouteStateStore.setState({
      lastProjectRouteById: {
        101: '/projects/101/run-monitor?compare=true',
      },
    });

    renderDashboard();

    await user.click(screen.getByRole('button', { name: 'Open' }));

    await waitFor(() => {
      expect(screen.getByTestId('project-run-monitor-route')).toBeInTheDocument();
    });
  });
});
