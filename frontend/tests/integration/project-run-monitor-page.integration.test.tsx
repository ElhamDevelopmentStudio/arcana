import { render, screen, within } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectRunMonitorPage } from '@/pages/projects/project-run-monitor-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useRunDetailQueryMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useRunDetailQuery: (...args: Parameters<typeof useRunDetailQueryMock>) =>
    useRunDetailQueryMock(...args),
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
});
