import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { mainRouter } from '@/router/main';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

describe('project workspace shell route', () => {
  beforeEach(() => {
    resetWorkspaceStore();
  });

  it('renders project workspace shell and nested home route at /projects/:project_id', async () => {
    const router = createMemoryRouter(mainRouter, {
      initialEntries: ['/projects/321'],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByTestId('project-workspace-shell')).toBeInTheDocument();
    expect(await screen.findByTestId('project-workspace-home')).toBeInTheDocument();
    expect(screen.getByTestId('project-workspace-shell-project-id')).toHaveTextContent('Project #321');
  });
});
