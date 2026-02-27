import { render, screen } from '@testing-library/react';
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

function renderProjectWorkspace(pathname: string) {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id',
        element: <ProjectWorkspaceShell />,
        children: [
          {
            index: true,
            element: <div data-testid="project-workspace-home">Workspace Home</div>,
          },
          {
            path: 'overview',
            element: <div data-testid="project-overview-route">Overview Route</div>,
          },
          {
            path: 'setup',
            element: <div data-testid="project-setup-route">Setup Route</div>,
          },
          {
            path: 'characters',
            element: <div data-testid="project-characters-route">Characters Route</div>,
          },
          {
            path: 'voice',
            element: <div data-testid="project-voice-route">Voice Route</div>,
          },
          {
            path: 'runs',
            element: <div data-testid="project-runs-route">Runs Route</div>,
          },
          {
            path: 'exports',
            element: <div data-testid="project-exports-route">Exports Route</div>,
          },
          {
            path: 'settings',
            element: <div data-testid="project-settings-route">Settings Route</div>,
          },
          {
            path: 'mode',
            element: <div data-testid="project-mode-route">Mode Route</div>,
          },
        ],
      },
    ],
    { initialEntries: [pathname] },
  );

  render(<RouterProvider router={router} />);
  return router;
}

describe('project workspace shell route', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectSetupStatusQueryMock.mockReset();
    useProjectAllowedActionsQueryMock.mockReset();
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: {
        is_complete: true,
        steps: [
          { step_id: 'ingestion', ready: true },
          { step_id: 'mode_selection', ready: true },
          { step_id: 'initial_run', ready: true },
          { step_id: 'character_mapping', ready: false },
          { step_id: 'voice_mapping', ready: false },
        ],
      },
    });
    useProjectAllowedActionsQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      data: {
        required_step: null,
        blocked_reason: null,
      },
    });
  });

  it('renders project workspace shell and nested home route at /projects/:project_id', async () => {
    renderProjectWorkspace('/projects/321');

    expect(await screen.findByTestId('project-workspace-shell')).toBeInTheDocument();
    expect(await screen.findByTestId('project-workspace-home')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-shell-project-id')).toHaveTextContent('Project #321');
  });

  it('renders grouped sidebar with stable project route mappings', async () => {
    const user = userEvent.setup();
    const router = renderProjectWorkspace('/projects/321/overview');

    expect(await screen.findByTestId('project-workspace-nav-group-foundation')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-nav-group-content')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-nav-group-operations')).toBeInTheDocument();

    expect(screen.getByTestId('project-workspace-nav-overview')).toHaveAttribute('href', '/projects/321/overview');
    expect(screen.getByTestId('project-workspace-nav-setup')).toHaveAttribute('href', '/projects/321/setup');
    expect(screen.getByTestId('project-workspace-nav-characters')).toHaveAttribute('href', '/projects/321/characters');
    expect(screen.getByTestId('project-workspace-nav-voice')).toHaveAttribute('href', '/projects/321/voice');
    expect(screen.getByTestId('project-workspace-nav-runs')).toHaveAttribute('href', '/projects/321/runs');
    expect(screen.getByTestId('project-workspace-nav-exports')).toHaveAttribute('href', '/projects/321/exports');
    expect(screen.getByTestId('project-workspace-nav-settings')).toHaveAttribute('href', '/projects/321/settings');

    await user.click(screen.getByTestId('project-workspace-nav-settings'));
    expect(await screen.findByTestId('project-settings-route')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/321/settings');
  });

  it('keeps mode route accessible when setup is incomplete', async () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: {
        is_complete: false,
        steps: [
          { step_id: 'ingestion', ready: false },
          { step_id: 'mode_selection', ready: false },
          { step_id: 'initial_run', ready: false },
          { step_id: 'character_mapping', ready: false },
          { step_id: 'voice_mapping', ready: false },
        ],
      },
    });

    const router = renderProjectWorkspace('/projects/321/mode');

    expect(await screen.findByTestId('project-mode-route')).toBeInTheDocument();
    expect(screen.queryByTestId('project-setup-route')).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/321/mode');
  });

  it('unlocks previously gated routes after setup completion transition', async () => {
    let isSetupComplete = false;
    useProjectSetupStatusQueryMock.mockImplementation(() => ({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: isSetupComplete
        ? {
            is_complete: true,
            steps: [
              { step_id: 'ingestion', ready: true },
              { step_id: 'mode_selection', ready: true },
              { step_id: 'initial_run', ready: true },
              { step_id: 'character_mapping', ready: true },
              { step_id: 'voice_mapping', ready: true },
            ],
          }
        : {
            is_complete: false,
            steps: [
              { step_id: 'ingestion', ready: true },
              { step_id: 'mode_selection', ready: true },
              { step_id: 'initial_run', ready: false },
              { step_id: 'character_mapping', ready: false },
              { step_id: 'voice_mapping', ready: false },
            ],
          },
    }));

    const router = renderProjectWorkspace('/projects/321/voice');

    expect(await screen.findByTestId('project-setup-route')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/321/setup');

    isSetupComplete = true;
    await router.navigate('/projects/321/voice');

    expect(await screen.findByTestId('project-voice-route')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-nav-voice')).not.toHaveAttribute('aria-disabled', 'true');
    expect(router.state.location.pathname).toBe('/projects/321/voice');
  });

  it('shows lock reason and blocks locked exports navigation using action gating metadata', async () => {
    const user = userEvent.setup();
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: {
        is_complete: false,
        steps: [
          { step_id: 'ingestion', ready: true },
          { step_id: 'mode_selection', ready: true },
          { step_id: 'initial_run', ready: false },
          { step_id: 'character_mapping', ready: false },
          { step_id: 'voice_mapping', ready: false },
        ],
      },
    });
    useProjectAllowedActionsQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      data: {
        required_step: 'initial_run',
        blocked_reason: 'An initial run is required (or must be rerun) before downstream actions are unlocked.',
      },
    });

    const router = renderProjectWorkspace('/projects/321/setup');

    expect(await screen.findByTestId('project-setup-route')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-nav-exports')).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByTestId('project-workspace-nav-locked-reason-exports')).toHaveTextContent(
      'An initial run is required (or must be rerun) before downstream actions are unlocked.',
    );

    await user.click(screen.getByTestId('project-workspace-nav-exports'));
    expect(router.state.location.pathname).toBe('/projects/321/setup');
  });

  it('shows deep-link guard panel on locked route with go-to-required-step action', async () => {
    const user = userEvent.setup();
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: {
        is_complete: true,
        steps: [
          { step_id: 'ingestion', ready: true },
          { step_id: 'mode_selection', ready: true },
          { step_id: 'initial_run', ready: true },
          { step_id: 'character_mapping', ready: true },
          { step_id: 'voice_mapping', ready: true },
        ],
      },
    });
    useProjectAllowedActionsQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      data: {
        required_step: 'restore',
        blocked_reason: 'Project is archived. Restore the project to continue workflow actions.',
      },
    });

    const router = renderProjectWorkspace('/projects/321/exports');

    expect(await screen.findByTestId('project-workspace-deep-link-guard')).toBeInTheDocument();
    expect(screen.queryByTestId('project-exports-route')).not.toBeInTheDocument();

    await user.click(screen.getByTestId('project-workspace-deep-link-guard-action'));
    expect(await screen.findByTestId('project-overview-route')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/321/overview');
  });
});
