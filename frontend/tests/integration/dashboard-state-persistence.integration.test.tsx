import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
  return router;
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

  it('applies dashboard filters and syncs them into URL params', async () => {
    const user = userEvent.setup();
    const router = renderDashboard();

    await waitFor(() => {
      expect(useProjectControlPanelProjectListQueryMock).toHaveBeenCalled();
    });

    await user.selectOptions(screen.getByTestId('dashboard-filter-status'), 'running');
    fireEvent.change(screen.getByTestId('dashboard-filter-selected-mode'), { target: { value: 'author' } });
    await user.selectOptions(screen.getByTestId('dashboard-filter-last-run-status'), 'failed');
    await user.selectOptions(screen.getByTestId('dashboard-filter-next-required-action'), 'export');

    await waitFor(() => {
      const lastCall = useProjectControlPanelProjectListQueryMock.mock.calls.at(-1);
      expect(lastCall?.[1]).toMatchObject({
        page: 1,
        page_size: 20,
        status: 'running',
        selected_mode: 'author',
        last_run_status: 'failed',
        next_required_action: 'export',
      });
      expect(router.state.location.search).toContain('status=running');
      expect(router.state.location.search).toContain('selected_mode=author');
      expect(router.state.location.search).toContain('last_run_status=failed');
      expect(router.state.location.search).toContain('next_required_action=export');
    });

    await user.click(screen.getByTestId('dashboard-filter-clear'));

    await waitFor(() => {
      const lastCall = useProjectControlPanelProjectListQueryMock.mock.calls.at(-1);
      expect(lastCall?.[1]).toMatchObject({
        page: 1,
        page_size: 20,
        status: undefined,
        selected_mode: undefined,
        last_run_status: undefined,
        next_required_action: undefined,
      });
      expect(router.state.location.search).toBe('?page=1&page_size=20');
    });
  });

  it('applies dashboard pagination controls and syncs URL params', async () => {
    const user = userEvent.setup();
    useProjectControlPanelProjectListQueryMock.mockImplementation((enabled: boolean, params: DashboardListQueryState) => {
      if (!enabled) {
        return { data: undefined };
      }
      return {
        data: {
          total_items: 45,
          page: params.page,
          page_size: params.page_size,
          has_next_page: params.page < 3,
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
      };
    });
    const router = renderDashboard();

    await waitFor(() => {
      expect(useProjectControlPanelProjectListQueryMock).toHaveBeenCalled();
    });

    await user.selectOptions(screen.getByTestId('dashboard-pagination-page-size'), '50');

    await waitFor(() => {
      const lastCall = useProjectControlPanelProjectListQueryMock.mock.calls.at(-1);
      expect(lastCall?.[1]).toMatchObject({
        page: 1,
        page_size: 50,
      });
      expect(router.state.location.search).toContain('page=1');
      expect(router.state.location.search).toContain('page_size=50');
    });

    await user.click(screen.getByTestId('dashboard-pagination-next'));

    await waitFor(() => {
      const lastCall = useProjectControlPanelProjectListQueryMock.mock.calls.at(-1);
      expect(lastCall?.[1]).toMatchObject({
        page: 2,
        page_size: 50,
      });
      expect(router.state.location.search).toContain('page=2');
      expect(router.state.location.search).toContain('page_size=50');
    });

    await user.click(screen.getByTestId('dashboard-pagination-prev'));

    await waitFor(() => {
      const lastCall = useProjectControlPanelProjectListQueryMock.mock.calls.at(-1);
      expect(lastCall?.[1]).toMatchObject({
        page: 1,
        page_size: 50,
      });
      expect(router.state.location.search).toContain('page=1');
      expect(router.state.location.search).toContain('page_size=50');
    });
  });
});
