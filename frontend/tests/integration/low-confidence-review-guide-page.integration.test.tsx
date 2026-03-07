import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectLowConfidenceReviewGuidePage } from '@/pages/projects/project-low-confidence-review-guide-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

function renderGuidePage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/guide/low-confidence-review',
        element: <ProjectLowConfidenceReviewGuidePage />,
      },
    ],
    { initialEntries: ['/projects/101/guide/low-confidence-review'] },
  );

  render(<RouterProvider router={router} />);
}

describe('low-confidence review guide page', () => {
  it('shows review workflow instructions and queue shortcut', () => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({ projectId: 101 });

    renderGuidePage();

    expect(screen.getByRole('heading', { level: 2, name: 'How to review low-confidence outputs' })).toBeInTheDocument();
    expect(screen.getByText('Goal of the queue')).toBeInTheDocument();
    expect(screen.getByText('Open low-confidence review queue')).toBeInTheDocument();
    expect(screen.getByTestId('low-confidence-guide-tip')).toBeInTheDocument();
  });
});
