import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectRunMonitorPage } from '@/pages/projects/project-run-monitor-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useRunDetailQueryMock = vi.fn();
const useRunConfigDiffQueryMock = vi.fn();
const useRunConfigPresetMutationMock = vi.fn();
const useRerunRunMutationMock = vi.fn();
const useRecoverRunMutationMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useRunDetailQuery: (...args: Parameters<typeof useRunDetailQueryMock>) =>
    useRunDetailQueryMock(...args),
  useRunConfigDiffQuery: (...args: Parameters<typeof useRunConfigDiffQueryMock>) =>
    useRunConfigDiffQueryMock(...args),
  useRunConfigPresetMutation: (...args: Parameters<typeof useRunConfigPresetMutationMock>) =>
    useRunConfigPresetMutationMock(...args),
  useRerunRunMutation: (...args: Parameters<typeof useRerunRunMutationMock>) =>
    useRerunRunMutationMock(...args),
  useRecoverRunMutation: (...args: Parameters<typeof useRecoverRunMutationMock>) =>
    useRecoverRunMutationMock(...args),
}));

function renderRunMonitorPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/run-monitor',
        element: <ProjectRunMonitorPage />,
      },
    ],
    { initialEntries: ['/projects/303/run-monitor'] },
  );

  render(<RouterProvider router={router} />);
}

function createRunDetail(overrides: Record<string, unknown> = {}) {
  return {
    run_id: 303,
    project_id: 303,
    status: 'completed',
    config: {},
    changelog_entries: [],
    started_at: '2025-01-01T00:00:00Z',
    finished_at: '2025-01-01T00:00:01Z',
    segment_count: 12,
    llm_calls: [],
    llm_cache_metrics: {},
    ...overrides,
  };
}

describe('project run monitor page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 303,
      projectTitle: 'Arcane Tension Project',
      selectedMode: 'author',
      chapterCount: 4,
      runId: 303,
    });
    useRunDetailQueryMock.mockReset();
    useRunConfigDiffQueryMock.mockReset();
    useRunConfigPresetMutationMock.mockReset();
    useRerunRunMutationMock.mockReset();
    useRecoverRunMutationMock.mockReset();
    useRunConfigDiffQueryMock.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    });
    useRunConfigPresetMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: vi.fn(),
    });
    useRerunRunMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: vi.fn().mockResolvedValue({
        run_id: 304,
        project_id: 303,
        status: 'completed',
        segment_count: 8,
      }),
    });
    useRecoverRunMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: vi.fn().mockResolvedValue({
        run_id: 305,
        project_id: 303,
        status: 'completed',
        segment_count: 8,
      }),
    });
  });

  it('displays degraded-mode banner when run is in rule-only mode', () => {
    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail({
        config: {
          llm_execution_mode: {
            mode: 'rule_only',
            reason: 'provider quota exhausted',
            provider: 'groq',
          },
        },
      }),
      isLoading: false,
      error: null,
    });

    renderRunMonitorPage();

    const banner = screen.getByTestId('llm-degraded-banner');
    expect(banner).toBeInTheDocument();
    expect(screen.getByText(/LLM availability is degraded/i)).toBeInTheDocument();
    expect(within(banner).getByText(/provider quota exhausted/i)).toBeInTheDocument();
    expect(within(banner).getByText(/groq/i)).toBeInTheDocument();
  });

  it('does not display degraded banner when execution mode is normal', () => {
    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail(),
      isLoading: false,
      error: null,
    });

    renderRunMonitorPage();

    expect(screen.queryByTestId('llm-degraded-banner')).not.toBeInTheDocument();
  });

  it('renders run config diff output when comparison data is available', () => {
    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail(),
      isLoading: false,
      error: null,
    });
    useRunConfigDiffQueryMock.mockReturnValue({
      data: {
        project_id: 303,
        base_run_id: 303,
        target_run_id: 304,
        base_config_schema_version: '1.0.0',
        target_config_schema_version: '1.0.0',
        is_identical: false,
        changed_fields: [
          {
            field: 'mode',
            base_value: 'author',
            target_value: 'academic',
          },
        ],
        base_only_fields: [],
        target_only_fields: ['deterministic_seed'],
      },
      isLoading: false,
      error: null,
    });

    renderRunMonitorPage();

    expect(screen.getByText(/Run Config Diff Viewer/i)).toBeInTheDocument();
    expect(screen.getByText(/"author" → "academic"/i)).toBeInTheDocument();
    expect(screen.getByText(/deterministic_seed/i)).toBeInTheDocument();
  });

  it('triggers rerun mutation from run monitor action bar', async () => {
    const user = userEvent.setup();
    const rerunTrigger = vi.fn().mockResolvedValue({
      run_id: 404,
      project_id: 303,
      status: 'completed',
      segment_count: 6,
    });
    useRerunRunMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: rerunTrigger,
    });
    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail(),
      isLoading: false,
      error: null,
    });

    renderRunMonitorPage();
    await user.click(screen.getByRole('button', { name: 'Rerun run' }));

    expect(rerunTrigger).toHaveBeenCalledTimes(1);
    expect(useWorkspaceStore.getState().runId).toBe(404);
  });

  it('triggers recover mutation from run monitor action bar', async () => {
    const user = userEvent.setup();
    const recoverTrigger = vi.fn().mockResolvedValue({
      run_id: 405,
      project_id: 303,
      status: 'completed',
      segment_count: 6,
    });
    useRecoverRunMutationMock.mockReturnValue({
      isMutating: false,
      error: null,
      trigger: recoverTrigger,
    });
    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail(),
      isLoading: false,
      error: null,
    });

    renderRunMonitorPage();
    await user.click(screen.getByRole('button', { name: 'Recover run' }));

    expect(recoverTrigger).toHaveBeenCalledTimes(1);
    expect(useWorkspaceStore.getState().runId).toBe(405);
  });
});
