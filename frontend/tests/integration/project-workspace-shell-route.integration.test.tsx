import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectWorkspaceShell } from '@/app/project-workspace-shell';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectSetupStatusQueryMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectSetupStatusQuery: (...args: Parameters<typeof useProjectSetupStatusQueryMock>) =>
    useProjectSetupStatusQueryMock(...args),
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
            path: 'setup',
            element: <div data-testid="project-setup-route">Setup Route</div>,
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
  });

  it('renders project workspace shell and nested home route at /projects/:project_id', async () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: {
        is_complete: true,
      },
    });
    renderProjectWorkspace('/projects/321');

    expect(await screen.findByTestId('project-workspace-shell')).toBeInTheDocument();
    expect(await screen.findByTestId('project-workspace-home')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-shell-project-id')).toHaveTextContent('Project #321');
  });

  it('redirects locked project sub-routes to setup when setup is incomplete', async () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
      data: {
        is_complete: false,
      },
    });

    const router = renderProjectWorkspace('/projects/321/mode');

    expect(await screen.findByTestId('project-setup-route')).toBeInTheDocument();
    expect(screen.queryByTestId('project-mode-route')).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/321/setup');
  });
});
