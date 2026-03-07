import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectExportPage } from '@/pages/projects/project-export-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useExportPayloadQueryMock = vi.fn();
const useExportCsvMutationMock = vi.fn();
const useRunDetailQueryMock = vi.fn();
const useCreateComparisonWorkspaceMutationMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useExportPayloadQuery: (...args: Parameters<typeof useExportPayloadQueryMock>) => useExportPayloadQueryMock(...args),
  useExportCsvMutation: (...args: Parameters<typeof useExportCsvMutationMock>) => useExportCsvMutationMock(...args),
  useRunDetailQuery: (...args: Parameters<typeof useRunDetailQueryMock>) => useRunDetailQueryMock(...args),
  useCreateComparisonWorkspaceMutation: (...args: Parameters<typeof useCreateComparisonWorkspaceMutationMock>) =>
    useCreateComparisonWorkspaceMutationMock(...args),
}));

function renderExportPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/export',
        element: <ProjectExportPage />,
      },
      {
        path: '/projects/:project_id/dashboards',
        element: <div data-testid="project-dashboards">Dashboards</div>,
      },
    ],
    { initialEntries: ['/projects/333/export'] },
  );

  render(<RouterProvider router={router} />);
}

describe('project export page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useExportPayloadQueryMock.mockReset();
    useExportCsvMutationMock.mockReset();
    useRunDetailQueryMock.mockReset();
    useCreateComparisonWorkspaceMutationMock.mockReset();
    useWorkspaceStore.setState({
      projectId: 333,
      projectTitle: 'Confidence Export Project',
      selectedMode: null,
      chapterCount: 2,
      runId: 900,
    });
    useExportPayloadQueryMock.mockReturnValue({
      data: {
        project_id: 333,
        project_title: 'Confidence Export Project',
        run_id: 900,
        status: 'complete',
        segments: [
          {
            segment_id: '333-001',
            chapter_id: 1,
            speaker: 'Mara',
            confidence: {
              speaker: 0.92,
              emotion: 0.81,
              type: 0.74,
            },
            tension_contribution: { confidence: 0.58 },
            dominance_contribution: { confidence: 0.67 },
            summary_tag: { confidence: 0.55 },
          },
          {
            segment_id: '333-002',
            chapter_id: 1,
            speaker: 'Narrator',
            confidence: {
              speaker: 0.98,
              emotion: 0.93,
              type: 0.86,
              tension: 0.77,
              dominance: 0.61,
            },
            summary_tag: { confidence: 0.9 },
          },
          {
            segment_id: '333-003',
            chapter_id: 2,
            speaker: 'Editor',
            confidence: {
              speaker: 0.99,
              emotion: 0.97,
              type: 0.95,
              tension: 0.95,
              dominance: 0.96,
            },
            summary_tag: { confidence: 0.95 },
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    useExportCsvMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: vi.fn().mockResolvedValue('segment_id,chapter_id\n333-001,1\n'),
    });
    useRunDetailQueryMock.mockReturnValue({
      data: {
        status: 'completed',
        config: {
          export_formats: ['json', 'csv'],
        },
      },
      isLoading: false,
      error: null,
    });
    useCreateComparisonWorkspaceMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: vi.fn().mockResolvedValue({
        workspace_id: 501,
        run_count: 0,
      }),
    });
  });

  it('renders major tag confidence for the first segments and keeps JSON preview available', () => {
    renderExportPage();

    expect(screen.getByText('Export Package')).toBeInTheDocument();
    expect(screen.getByText('Project: 333')).toBeInTheDocument();
    expect(screen.getByText('Run: 900')).toBeInTheDocument();

    const firstRow = screen.getByTestId('export-confidence-row-333-001');
    expect(firstRow).toHaveTextContent('Ch 1 / 333-001');
    expect(firstRow).toHaveTextContent('92%');
    expect(firstRow).toHaveTextContent('81%');
    expect(firstRow).toHaveTextContent('74%');
    expect(firstRow).toHaveTextContent('58%');
    expect(firstRow).toHaveTextContent('67%');
    expect(firstRow).toHaveTextContent('55%');

    expect(screen.getByText(/"project_id":\s+333/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download JSON/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download CSV/i })).toBeInTheDocument();
  });

  it('links to dashboards step', async () => {
    renderExportPage();
    const driver = userEvent.setup();

    await driver.click(screen.getByRole('button', { name: 'Continue to Dashboards' }));
    expect(screen.getByTestId('project-dashboards')).toBeInTheDocument();
  });

  it('filters confidence rows by configurable threshold and orientation', async () => {
    const user = userEvent.setup();
    renderExportPage();

    expect(screen.getByText('Showing 2 rows where min confidence is below 80%')).toBeInTheDocument();
    expect(screen.getByTestId('export-confidence-row-333-001')).toBeInTheDocument();
    expect(screen.getByTestId('export-confidence-row-333-002')).toBeInTheDocument();
    expect(screen.queryByTestId('export-confidence-row-333-003')).not.toBeInTheDocument();

    const threshold = screen.getByTestId('export-confidence-threshold');
    fireEvent.change(threshold, { target: { value: '0.9' } });

    expect(screen.getByText('Showing 2 rows where min confidence is below 90%')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Show at or above threshold' }));
    expect(screen.getByText('Showing 1 rows where min confidence is at least 90%')).toBeInTheDocument();
    expect(screen.getByTestId('export-confidence-row-333-003')).toBeInTheDocument();
    expect(screen.queryByTestId('export-confidence-row-333-001')).not.toBeInTheDocument();
  });

  it('triggers CSV export mutation from export page', async () => {
    const user = userEvent.setup();
    const csvTrigger = vi.fn().mockResolvedValue('segment_id,chapter_id\n333-001,1\n');
    useExportCsvMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: csvTrigger,
    });

    renderExportPage();
    await user.click(screen.getByRole('button', { name: /Download CSV/i }));

    expect(csvTrigger).toHaveBeenCalledTimes(1);
  });

  it('gates export actions by run status and allowed formats', () => {
    useRunDetailQueryMock.mockReturnValue({
      data: {
        status: 'running',
        config: {
          export_formats: ['json'],
        },
      },
      isLoading: false,
      error: null,
    });

    renderExportPage();

    expect(screen.getByText('Exports are unavailable while run status is running.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download JSON/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Download CSV/i })).toBeDisabled();
  });

  it('keeps JSON enabled and disables CSV when run format allow-list excludes csv', () => {
    useRunDetailQueryMock.mockReturnValue({
      data: {
        status: 'completed',
        config: {
          export_formats: ['json'],
        },
      },
      isLoading: false,
      error: null,
    });

    renderExportPage();

    expect(screen.getByRole('button', { name: /Download JSON/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Download CSV/i })).toBeDisabled();
    expect(screen.getByText('CSV export is disabled for this run configuration.')).toBeInTheDocument();
  });

  it('creates comparison workspace from export page', async () => {
    const user = userEvent.setup();
    const createWorkspaceTrigger = vi.fn().mockResolvedValue({
      workspace_id: 777,
      run_count: 0,
    });
    useCreateComparisonWorkspaceMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: createWorkspaceTrigger,
    });

    renderExportPage();
    await user.type(screen.getByTestId('comparison-workspace-name-input'), 'Cross-run analysis pack');
    await user.click(screen.getByTestId('comparison-workspace-create-button'));

    expect(createWorkspaceTrigger).toHaveBeenCalledWith({ name: 'Cross-run analysis pack' });
    expect(screen.getByTestId('comparison-workspace-created-id')).toHaveTextContent('Workspace created: #777');
  });
});
