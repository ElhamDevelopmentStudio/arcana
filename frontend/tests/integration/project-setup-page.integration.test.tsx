import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectSetupPage } from '@/pages/projects/project-setup-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectSetupStatusQueryMock = vi.fn();
const setupStatusMutateMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectSetupStatusQuery: (...args: Parameters<typeof useProjectSetupStatusQueryMock>) =>
    useProjectSetupStatusQueryMock(...args),
}));

function renderProjectSetupPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/setup',
        element: <ProjectSetupPage />,
      },
      {
        path: '/projects/:project_id/overview',
        element: <div data-testid="project-overview-route">Project overview route</div>,
      },
    ],
    { initialEntries: ['/projects/77/setup'] },
  );

  render(<RouterProvider router={router} />);
  return router;
}

describe('project setup page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectSetupStatusQueryMock.mockReset();
    setupStatusMutateMock.mockReset();
  });

  it('renders loading state while setup status is pending', () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: true,
      data: undefined,
      error: undefined,
      mutate: setupStatusMutateMock,
    });

    renderProjectSetupPage();

    expect(screen.getByTestId('project-setup-loading')).toBeInTheDocument();
  });

  it('renders retryable setup-status error state', async () => {
    const user = userEvent.setup();
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      data: undefined,
      error: new Error('setup status failed'),
      mutate: setupStatusMutateMock,
    });

    renderProjectSetupPage();

    expect(screen.getByTestId('project-setup-error')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry setup status' }));
    expect(setupStatusMutateMock).toHaveBeenCalledTimes(1);
  });

  it('renders backend-driven setup checklist rows', () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'ingested',
        next_required_action: 'select_mode',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    expect(screen.getByTestId('project-setup-ready')).toBeInTheDocument();
    expect(screen.getByText('Setup in progress')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-step-ingestion')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-step-mode_selection')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-step-initial_run')).toBeInTheDocument();
    expect(screen.getByText('Mode Selection')).toBeInTheDocument();
  });

  it('redirects to project overview when setup is complete', async () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'configured',
        next_required_action: 'run',
        is_complete: true,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: true, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: true, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    const router = renderProjectSetupPage();

    expect(await screen.findByTestId('project-overview-route')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/77/overview');
  });
});
