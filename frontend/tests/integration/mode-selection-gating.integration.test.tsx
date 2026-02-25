import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useModeCatalogQuery: () => ({
    data: {
      modes: ['audiobook', 'academic', 'author', 'custom'],
      default_mode: 'audiobook',
      persisted_in: ['projects.selected_mode'],
    },
    isLoading: false,
    error: null,
  }),
  useRunDetailQuery: () => ({
    data: undefined,
    isLoading: false,
    error: null,
  }),
}));

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectModePage } from '@/pages/projects/project-mode-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

function renderModePage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/mode',
        element: <ProjectModePage />,
      },
      {
        path: '/projects/:project_id/characters',
        element: <div data-testid="characters-page">Character page</div>,
      },
    ],
    { initialEntries: ['/projects/101/mode'] },
  );

  render(<RouterProvider router={router} />);
}

describe('mode selection gating', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 101,
      projectTitle: 'Shadow Slave',
      selectedMode: null,
      chapterCount: 12,
      runId: null,
    });
  });

  it('keeps continue action locked until a mode is explicitly selected', async () => {
    const user = userEvent.setup();
    renderModePage();

    const continueButton = screen.getByTestId('mode-continue-button');
    expect(continueButton).toBeDisabled();
    expect(screen.getByTestId('mode-required-hint')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/select mode/i), 'author');
    expect(continueButton).toBeEnabled();

    await user.click(continueButton);
    expect(screen.getByTestId('characters-page')).toBeInTheDocument();
  });
});
