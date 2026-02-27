import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { ComparisonWorkspaceDetailPage } from '@/pages/comparison/comparison-workspace-detail-page';

const useComparisonWorkspaceDetailQueryMock = vi.fn();
const useComparisonWorkspaceAlignedCurvesQueryMock = vi.fn();
const useComparisonWorkspaceComparativeDatasetMutationMock = vi.fn();
const useAddRunToComparisonWorkspaceMutationMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useComparisonWorkspaceDetailQuery: (...args: Parameters<typeof useComparisonWorkspaceDetailQueryMock>) =>
    useComparisonWorkspaceDetailQueryMock(...args),
  useComparisonWorkspaceAlignedCurvesQuery: (
    ...args: Parameters<typeof useComparisonWorkspaceAlignedCurvesQueryMock>
  ) => useComparisonWorkspaceAlignedCurvesQueryMock(...args),
  useComparisonWorkspaceComparativeDatasetMutation: (
    ...args: Parameters<typeof useComparisonWorkspaceComparativeDatasetMutationMock>
  ) => useComparisonWorkspaceComparativeDatasetMutationMock(...args),
  useAddRunToComparisonWorkspaceMutation: (
    ...args: Parameters<typeof useAddRunToComparisonWorkspaceMutationMock>
  ) => useAddRunToComparisonWorkspaceMutationMock(...args),
}));

function renderWorkspaceDetailPage(pathname: string) {
  const router = createMemoryRouter(
    [
      {
        path: '/comparison-workspaces/:workspace_id',
        element: <ComparisonWorkspaceDetailPage />,
      },
    ],
    { initialEntries: [pathname] },
  );
  render(<RouterProvider router={router} />);
}

describe('comparison workspace detail page', () => {
  it('renders workspace detail with linked run table', () => {
    useComparisonWorkspaceDetailQueryMock.mockReturnValue({
      data: {
        workspace_id: 42,
        name: 'Cross-run validation pack',
        run_count: 1,
        runs: [
          {
            project_id: 333,
            run_id: 900,
            status: 'completed',
            project_title: 'Confidence Export Project',
          },
        ],
      },
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    useAddRunToComparisonWorkspaceMutationMock.mockReturnValue({
      trigger: vi.fn(),
      isMutating: false,
    });
    useComparisonWorkspaceAlignedCurvesQueryMock.mockReturnValue({
      data: {
        workspace_id: 42,
        run_count: 1,
        aligned_points: 32,
        metrics: [
          {
            metric_id: 'normalized_pacing_signature',
            points_per_run: [{ run_id: 900, project_id: 333, status: 'completed', points: [0.1, 0.2, 0.3] }],
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    useComparisonWorkspaceComparativeDatasetMutationMock.mockReturnValue({
      trigger: vi.fn(),
      isMutating: false,
    });

    renderWorkspaceDetailPage('/comparison-workspaces/42');

    expect(screen.getByRole('heading', { name: 'Comparison Workspace' })).toBeInTheDocument();
    expect(screen.getByText('Workspace:')).toBeInTheDocument();
    expect(screen.getByText('#42')).toBeInTheDocument();
    expect(screen.getByText('Cross-run validation pack')).toBeInTheDocument();
    expect(screen.getByText('Run #900')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('Aligned Curves Analysis')).toBeInTheDocument();
    expect(screen.getByText('normalized_pacing_signature')).toBeInTheDocument();
    expect(screen.getByText('32')).toBeInTheDocument();
  });

  it('links a run and revalidates workspace detail', async () => {
    const mutateMock = vi.fn().mockResolvedValue(undefined);
    const triggerMock = vi.fn().mockResolvedValue({
      workspace_id: 42,
      run_count: 1,
      runs: [
        {
          project_id: 333,
          run_id: 900,
          status: 'completed',
        },
      ],
    });

    useComparisonWorkspaceDetailQueryMock.mockReturnValue({
      data: {
        workspace_id: 42,
        name: 'Cross-run validation pack',
        run_count: 0,
        runs: [],
      },
      isLoading: false,
      error: null,
      mutate: mutateMock,
    });
    useAddRunToComparisonWorkspaceMutationMock.mockReturnValue({
      trigger: triggerMock,
      isMutating: false,
    });
    useComparisonWorkspaceAlignedCurvesQueryMock.mockReturnValue({
      data: {
        workspace_id: 42,
        run_count: 0,
        aligned_points: 32,
        metrics: [],
      },
      isLoading: false,
      error: null,
    });
    useComparisonWorkspaceComparativeDatasetMutationMock.mockReturnValue({
      trigger: vi.fn(),
      isMutating: false,
    });

    renderWorkspaceDetailPage('/comparison-workspaces/42');

    fireEvent.change(screen.getByTestId('comparison-workspace-link-project-id-input'), {
      target: { value: '333' },
    });
    fireEvent.change(screen.getByTestId('comparison-workspace-link-run-id-input'), {
      target: { value: '900' },
    });
    fireEvent.click(screen.getByTestId('comparison-workspace-link-run-button'));

    await waitFor(() => {
      expect(triggerMock).toHaveBeenCalledWith({ project_id: 333, run_id: 900 });
    });
    await waitFor(() => {
      expect(mutateMock).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByTestId('comparison-workspace-link-success')).toHaveTextContent(
      'Run #900 linked to workspace #42.',
    );
  });

  it('retrieves comparative dataset export and renders summary', async () => {
    const triggerMock = vi.fn().mockResolvedValue({
      workspace_id: 42,
      workspace_name: 'Cross-run validation pack',
      generated_at: '2026-02-27T22:00:00Z',
      run_count: 1,
      aligned_points: 32,
      metrics: [{ metric_id: 'chapter_valence_mean', points_per_run: [] }],
      runs: [
        {
          run_id: 900,
          project_id: 333,
          project_title: 'Confidence Export Project',
          status: 'completed',
          segment_count: 53,
          run_config_mode: 'author',
          academic_reports: {},
          comparative_run_metrics_snapshot: {},
          academic_export_manifest: {},
        },
      ],
    });

    useComparisonWorkspaceDetailQueryMock.mockReturnValue({
      data: {
        workspace_id: 42,
        name: 'Cross-run validation pack',
        run_count: 1,
        runs: [
          {
            project_id: 333,
            run_id: 900,
            status: 'completed',
          },
        ],
      },
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    useAddRunToComparisonWorkspaceMutationMock.mockReturnValue({
      trigger: vi.fn(),
      isMutating: false,
    });
    useComparisonWorkspaceAlignedCurvesQueryMock.mockReturnValue({
      data: {
        workspace_id: 42,
        run_count: 1,
        aligned_points: 32,
        metrics: [],
      },
      isLoading: false,
      error: null,
    });
    useComparisonWorkspaceComparativeDatasetMutationMock.mockReturnValue({
      trigger: triggerMock,
      isMutating: false,
    });

    renderWorkspaceDetailPage('/comparison-workspaces/42');

    fireEvent.click(screen.getByTestId('comparison-workspace-export-fetch-button'));

    await waitFor(() => {
      expect(triggerMock).toHaveBeenCalledWith({});
    });
    await waitFor(() => {
      expect(screen.getByTestId('comparison-workspace-export-summary')).toBeInTheDocument();
    });
    expect(screen.getByText('2026-02-27T22:00:00Z')).toBeInTheDocument();
  });
});
