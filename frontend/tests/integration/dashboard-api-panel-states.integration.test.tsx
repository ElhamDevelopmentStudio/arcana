import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DashboardPage } from '@/pages/dashboard/dashboard-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectControlPanelSummaryQueryMock = vi.fn();
const useProjectControlPanelProjectListQueryMock = vi.fn();
const useProjectAllowedActionsQueryMock = vi.fn();
const summaryMutateMock = vi.fn();
const listMutateMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectControlPanelSummaryQuery: (...args: Parameters<typeof useProjectControlPanelSummaryQueryMock>) =>
    useProjectControlPanelSummaryQueryMock(...args),
  useProjectControlPanelProjectListQuery: (...args: Parameters<typeof useProjectControlPanelProjectListQueryMock>) =>
    useProjectControlPanelProjectListQueryMock(...args),
  useProjectAllowedActionsQuery: (...args: Parameters<typeof useProjectAllowedActionsQueryMock>) =>
    useProjectAllowedActionsQueryMock(...args),
}));

function renderDashboard() {
  const router = createMemoryRouter(
    [
      {
        path: '/dashboard',
        element: <DashboardPage />,
      },
      {
        path: '/projects/new',
        element: <div data-testid="project-new-page">Project new</div>,
      },
    ],
    { initialEntries: ['/dashboard'] },
  );
  render(<RouterProvider router={router} />);
}

describe('dashboard api panel state primitives', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectControlPanelSummaryQueryMock.mockReset();
    useProjectControlPanelProjectListQueryMock.mockReset();
    useProjectAllowedActionsQueryMock.mockReset();
    summaryMutateMock.mockReset();
    listMutateMock.mockReset();
    useProjectAllowedActionsQueryMock.mockReturnValue({
      data: {
        allowed_actions: ['run'],
      },
      isLoading: false,
      error: undefined,
    });
  });

  it('renders loading states for summary and list panels', () => {
    useProjectControlPanelSummaryQueryMock.mockReturnValue({
      isLoading: true,
      data: undefined,
      error: undefined,
      mutate: summaryMutateMock,
    });
    useProjectControlPanelProjectListQueryMock.mockReturnValue({
      isLoading: true,
      data: undefined,
      error: undefined,
      mutate: listMutateMock,
    });

    renderDashboard();

    expect(screen.getByTestId('dashboard-summary-loading')).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-list-loading')).toBeInTheDocument();
  });

  it('renders retryable error states and triggers retry callbacks', async () => {
    const user = userEvent.setup();
    useProjectControlPanelSummaryQueryMock.mockReturnValue({
      isLoading: false,
      data: undefined,
      error: new Error('summary failed'),
      mutate: summaryMutateMock,
    });
    useProjectControlPanelProjectListQueryMock.mockReturnValue({
      isLoading: false,
      data: undefined,
      error: new Error('list failed'),
      mutate: listMutateMock,
    });

    renderDashboard();

    expect(screen.getByTestId('dashboard-summary-error')).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-list-error')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry summary' }));
    await user.click(screen.getByRole('button', { name: 'Retry projects list' }));

    expect(summaryMutateMock).toHaveBeenCalledTimes(1);
    expect(listMutateMock).toHaveBeenCalledTimes(1);
  });

  it('renders standardized empty state when list has no items', async () => {
    useProjectControlPanelSummaryQueryMock.mockReturnValue({
      isLoading: false,
      data: {
        total_projects: 0,
        active_run_count: 0,
        recent_failure_count: 0,
      },
      error: undefined,
      mutate: summaryMutateMock,
    });
    useProjectControlPanelProjectListQueryMock.mockReturnValue({
      isLoading: false,
      data: { items: [] },
      error: undefined,
      mutate: listMutateMock,
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-list-empty')).toBeInTheDocument();
    });
    expect(screen.getByText('No projects available')).toBeInTheDocument();
    expect(screen.getByText('No projects found.')).toBeInTheDocument();
  });
});
