import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectDashboardsPage } from '@/pages/projects/project-dashboards-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useExportPayloadQuery: () => ({
    data: {
      project_id: 202,
      project_title: 'Arcane Tension Project',
      run_id: 88,
      status: 'complete',
      segments: [
        {
          segment_id: '202-001',
          chapter_id: 1,
          segment_index: 1,
          tension_contribution: { value: 0.1 },
        },
        {
          segment_id: '202-002',
          chapter_id: 1,
          segment_index: 2,
          tension_contribution: { value: 0.2 },
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
  useTensionGraphQuery: () => ({
    data: {
      metric_id: 'smoothed_tension_curve',
      metric_label: 'Smoothed tension curve',
      source_path: ['smoothed_tension_curve', 'tension_curve'],
      value_key: 'smoothed_tension',
      points: [
        { position: 1, smoothed_tension: 0.25, segment_id: '202-001' },
        { position: 2, smoothed_tension: 0.35, segment_id: '202-002' },
      ],
      peak_markers: [],
      plateau_regions: [],
      metadata: {},
    },
    isLoading: false,
    error: null,
  }),
}));

function renderDashboardPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/dashboards',
        element: <ProjectDashboardsPage />,
      },
    ],
    { initialEntries: ['/projects/202/dashboards'] },
  );
  render(<RouterProvider router={router} />);
}

describe('project dashboards page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 202,
      projectTitle: 'Arcane Tension Project',
      selectedMode: null,
      chapterCount: null,
      runId: 88,
    });
  });

  it('renders smoothed and raw tension series with a mode toggle', async () => {
    const user = userEvent.setup();
    renderDashboardPage();

    expect(screen.getByText('Data source: run tension graph endpoint')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /tension smoothing toggle/i })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('dashboards-tension-202-001')).toHaveTextContent('T 25%');

    await user.click(screen.getByRole('switch', { name: /tension smoothing toggle/i }));

    expect(screen.getByRole('switch', { name: /tension smoothing toggle/i })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByText('Data source: raw segment tension')).toBeInTheDocument();
    expect(screen.getByTestId('dashboards-tension-202-001')).toHaveTextContent('T 10%');
  });
});
