import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectWorkspaceShell } from '@/app/project-workspace-shell';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectSetupStatusQueryMock = vi.fn();
const useProjectAllowedActionsQueryMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectSetupStatusQuery: (...args: Parameters<typeof useProjectSetupStatusQueryMock>) =>
    useProjectSetupStatusQueryMock(...args),
  useProjectAllowedActionsQuery: (...args: Parameters<typeof useProjectAllowedActionsQueryMock>) =>
    useProjectAllowedActionsQueryMock(...args),
}));

type SetupSnapshot = {
  is_complete: boolean;
  steps: Array<{ step_id: string; ready: boolean }>;
};

type ActionsSnapshot = {
  required_step: string | null;
  blocked_reason: string | null;
};

let setupSnapshot: SetupSnapshot;
let actionsSnapshot: ActionsSnapshot;

function renderWorkspace(pathname: string) {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id',
        element: <ProjectWorkspaceShell />,
        children: [
          {
            path: 'setup',
            element: <div data-testid="workspace-setup-route">Setup route</div>,
          },
          {
            path: 'voice',
            element: <div data-testid="workspace-voice-route">Voice route</div>,
          },
          {
            path: 'runs',
            element: <div data-testid="workspace-runs-route">Runs route</div>,
          },
          {
            path: 'exports',
            element: <div data-testid="workspace-exports-route">Exports route</div>,
          },
          {
            path: 'overview',
            element: <div data-testid="workspace-overview-route">Overview route</div>,
          },
        ],
      },
    ],
    { initialEntries: [pathname] },
  );

  render(<RouterProvider router={router} />);
  return router;
}

describe('project workspace setup-gate and deep-link guard integration', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectSetupStatusQueryMock.mockReset();
    useProjectAllowedActionsQueryMock.mockReset();

    setupSnapshot = {
      is_complete: true,
      steps: [
        { step_id: 'ingestion', ready: true },
        { step_id: 'mode_selection', ready: true },
        { step_id: 'initial_run', ready: true },
        { step_id: 'character_mapping', ready: true },
        { step_id: 'voice_mapping', ready: true },
      ],
    };
    actionsSnapshot = {
      required_step: null,
      blocked_reason: null,
    };

    useProjectSetupStatusQueryMock.mockImplementation(() => ({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: setupSnapshot,
    }));
    useProjectAllowedActionsQueryMock.mockImplementation(() => ({
      isLoading: false,
      error: undefined,
      data: actionsSnapshot,
    }));
  });

  it('redirects locked sub-routes to setup when setup is incomplete', async () => {
    setupSnapshot = {
      is_complete: false,
      steps: [
        { step_id: 'ingestion', ready: false },
        { step_id: 'mode_selection', ready: false },
        { step_id: 'initial_run', ready: false },
        { step_id: 'character_mapping', ready: false },
        { step_id: 'voice_mapping', ready: false },
      ],
    };

    const router = renderWorkspace('/projects/321/voice');

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/projects/321/setup');
    });
    expect(screen.getByTestId('workspace-setup-route')).toBeInTheDocument();
    expect(screen.queryByTestId('workspace-voice-route')).not.toBeInTheDocument();
  });

  it('unlocks previously gated route after setup transition to complete', async () => {
    setupSnapshot = {
      is_complete: false,
      steps: [
        { step_id: 'ingestion', ready: false },
        { step_id: 'mode_selection', ready: false },
        { step_id: 'initial_run', ready: false },
        { step_id: 'character_mapping', ready: false },
        { step_id: 'voice_mapping', ready: false },
      ],
    };

    const router = renderWorkspace('/projects/321/voice');
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/projects/321/setup');
    });

    setupSnapshot = {
      is_complete: true,
      steps: [
        { step_id: 'ingestion', ready: true },
        { step_id: 'mode_selection', ready: true },
        { step_id: 'initial_run', ready: true },
        { step_id: 'character_mapping', ready: true },
        { step_id: 'voice_mapping', ready: true },
      ],
    };

    await router.navigate('/projects/321/voice');
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/projects/321/voice');
    });
    expect(screen.getByTestId('workspace-voice-route')).toBeInTheDocument();
    expect(screen.queryByTestId('project-workspace-deep-link-guard')).not.toBeInTheDocument();
  });

  it('shows deep-link guard and routes to required step action target', async () => {
    const user = userEvent.setup();
    actionsSnapshot = {
      required_step: 'initial_run',
      blocked_reason: 'An initial run is required (or must be rerun) before downstream actions are unlocked.',
    };

    const router = renderWorkspace('/projects/321/exports');

    expect(await screen.findByTestId('project-workspace-deep-link-guard')).toBeInTheDocument();
    expect(screen.queryByTestId('workspace-exports-route')).not.toBeInTheDocument();

    await user.click(screen.getByTestId('project-workspace-deep-link-guard-action'));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/projects/321/runs');
    });
    expect(screen.getByTestId('workspace-runs-route')).toBeInTheDocument();
  });
});
