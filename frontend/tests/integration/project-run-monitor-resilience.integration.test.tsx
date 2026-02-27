import { render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectRunMonitorPage } from '@/pages/projects/project-run-monitor-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useRunDetailQueryMock = vi.fn();
const useRunConfigDiffQueryMock = vi.fn();
const useRunConfigPresetMutationMock = vi.fn();
const useRerunRunMutationMock = vi.fn();
const useRecoverRunMutationMock = vi.fn();
const useCancelRunMutationMock = vi.fn();
const useAudiobookPrepDashboardQueryMock = vi.fn();
const useCharacterAnalyticsQueryMock = vi.fn();
const useCharacterCooccurrenceGraphQueryMock = vi.fn();
const usePipelineStageDurationsDashboardQueryMock = vi.fn();
const useTensionGraphQueryMock = vi.fn();
const usePolarityGraphQueryMock = vi.fn();

const runMutationRecoveryStorageKey = 'nipe-run-monitor-pending-mutation';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useRunDetailQuery: (...args: Parameters<typeof useRunDetailQueryMock>) => useRunDetailQueryMock(...args),
  useRunConfigDiffQuery: (...args: Parameters<typeof useRunConfigDiffQueryMock>) => useRunConfigDiffQueryMock(...args),
  useRunConfigPresetMutation: (...args: Parameters<typeof useRunConfigPresetMutationMock>) =>
    useRunConfigPresetMutationMock(...args),
  useRerunRunMutation: (...args: Parameters<typeof useRerunRunMutationMock>) => useRerunRunMutationMock(...args),
  useRecoverRunMutation: (...args: Parameters<typeof useRecoverRunMutationMock>) =>
    useRecoverRunMutationMock(...args),
  useCancelRunMutation: (...args: Parameters<typeof useCancelRunMutationMock>) => useCancelRunMutationMock(...args),
  useAudiobookPrepDashboardQuery: (...args: Parameters<typeof useAudiobookPrepDashboardQueryMock>) =>
    useAudiobookPrepDashboardQueryMock(...args),
  useCharacterAnalyticsQuery: (...args: Parameters<typeof useCharacterAnalyticsQueryMock>) =>
    useCharacterAnalyticsQueryMock(...args),
  useCharacterCooccurrenceGraphQuery: (...args: Parameters<typeof useCharacterCooccurrenceGraphQueryMock>) =>
    useCharacterCooccurrenceGraphQueryMock(...args),
  usePipelineStageDurationsDashboardQuery: (...args: Parameters<typeof usePipelineStageDurationsDashboardQueryMock>) =>
    usePipelineStageDurationsDashboardQueryMock(...args),
  useTensionGraphQuery: (...args: Parameters<typeof useTensionGraphQueryMock>) => useTensionGraphQueryMock(...args),
  usePolarityGraphQuery: (...args: Parameters<typeof usePolarityGraphQueryMock>) => usePolarityGraphQueryMock(...args),
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

function createRunDetail(status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled') {
  return {
    run_id: 303,
    project_id: 303,
    status,
    config: {},
    changelog_entries: [],
    started_at: '2026-02-27T00:00:00Z',
    finished_at: status === 'queued' || status === 'running' ? null : '2026-02-27T00:01:00Z',
    segment_count: 12,
    llm_calls: [],
    llm_cache_metrics: {},
  };
}

describe('project run monitor resilience behavior', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    window.sessionStorage.removeItem(runMutationRecoveryStorageKey);
    useWorkspaceStore.setState({
      projectId: 303,
      projectTitle: 'Resilience Project',
      selectedMode: 'author',
      chapterCount: 4,
      runId: 303,
    });

    useRunConfigDiffQueryMock.mockReturnValue({ data: null, isLoading: false, error: null });
    useRunConfigPresetMutationMock.mockReturnValue({ isMutating: false, error: null, data: undefined, trigger: vi.fn() });
    useRerunRunMutationMock.mockReturnValue({ isMutating: false, error: null, trigger: vi.fn() });
    useRecoverRunMutationMock.mockReturnValue({ isMutating: false, error: null, trigger: vi.fn() });
    useCancelRunMutationMock.mockReturnValue({ isMutating: false, error: null, trigger: vi.fn() });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('restores pending mutation from session storage and locks run action buttons', async () => {
    const runDetailMutate = vi.fn();
    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail('running'),
      isLoading: false,
      error: null,
      mutate: runDetailMutate,
    });
    useAudiobookPrepDashboardQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    useCharacterAnalyticsQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    useCharacterCooccurrenceGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    useTensionGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    usePolarityGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    usePipelineStageDurationsDashboardQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });

    window.sessionStorage.setItem(
      runMutationRecoveryStorageKey,
      JSON.stringify({
        projectId: 303,
        sourceRunId: 303,
        trackedRunId: 303,
        mutation: 'rerun',
        startedAt: new Date().toISOString(),
      }),
    );

    renderRunMonitorPage();

    await waitFor(() => {
      expect(screen.getByTestId('run-monitor-mutation-recovery-banner')).toBeInTheDocument();
    });
    expect(screen.getByTestId('run-monitor-refresh-state')).toHaveTextContent('active');
    expect(screen.getByRole('button', { name: 'Rerun run' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Recover run' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel run' })).toBeDisabled();
  });

  it('clears pending mutation recovery when tracked run reaches terminal state', async () => {
    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail('completed'),
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    useAudiobookPrepDashboardQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    useCharacterAnalyticsQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    useCharacterCooccurrenceGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    useTensionGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    usePolarityGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });
    usePipelineStageDurationsDashboardQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: vi.fn() });

    window.sessionStorage.setItem(
      runMutationRecoveryStorageKey,
      JSON.stringify({
        projectId: 303,
        sourceRunId: 303,
        trackedRunId: 303,
        mutation: 'recover',
        startedAt: new Date().toISOString(),
      }),
    );

    renderRunMonitorPage();

    await waitFor(() => {
      expect(window.sessionStorage.getItem(runMutationRecoveryStorageKey)).toBeNull();
    });
    expect(screen.queryByTestId('run-monitor-mutation-recovery-banner')).not.toBeInTheDocument();
  });

  it('refreshes run monitor queries on interval while run is active', async () => {
    vi.useFakeTimers();
    const runDetailMutate = vi.fn();
    const audiobookMutate = vi.fn();
    const analyticsMutate = vi.fn();
    const cooccurrenceMutate = vi.fn();
    const tensionMutate = vi.fn();
    const polarityMutate = vi.fn();
    const stageDurationMutate = vi.fn();

    useRunDetailQueryMock.mockReturnValue({
      data: createRunDetail('running'),
      isLoading: false,
      error: null,
      mutate: runDetailMutate,
    });
    useAudiobookPrepDashboardQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: audiobookMutate });
    useCharacterAnalyticsQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: analyticsMutate });
    useCharacterCooccurrenceGraphQueryMock.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
      mutate: cooccurrenceMutate,
    });
    useTensionGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: tensionMutate });
    usePolarityGraphQueryMock.mockReturnValue({ data: null, isLoading: false, error: null, mutate: polarityMutate });
    usePipelineStageDurationsDashboardQueryMock.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
      mutate: stageDurationMutate,
    });

    renderRunMonitorPage();

    await vi.advanceTimersByTimeAsync(4200);

    expect(runDetailMutate).toHaveBeenCalled();
    expect(audiobookMutate).toHaveBeenCalled();
    expect(analyticsMutate).toHaveBeenCalled();
    expect(cooccurrenceMutate).toHaveBeenCalled();
    expect(tensionMutate).toHaveBeenCalled();
    expect(polarityMutate).toHaveBeenCalled();
    expect(stageDurationMutate).toHaveBeenCalled();
  });
});
