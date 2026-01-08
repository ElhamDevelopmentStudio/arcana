import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectSpeakerReviewPage } from '@/pages/projects/project-speaker-review-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useExportPayloadQuery: () => ({
    data: {
      project_id: 101,
      project_title: 'Arcane Project',
      run_id: 77,
      status: 'complete',
      segments: [
        {
          segment_id: '101-001',
          chapter_id: 1,
          segment_index: 1,
          original_text: 'Kai opened the door and said, “Welcome in.”',
          speaker: 'Kai',
          speaker_id: 42,
          speaker_state: 'uncertain',
          speaker_evidence: { rule: 'quoted_prefix', score: 0.72 },
          confidence: {
            speaker: 0.62,
          },
        },
        {
          segment_id: '101-002',
          chapter_id: 1,
          segment_index: 2,
          original_text: 'Rain hammered the deck as the captain signaled.',
          speaker: 'Narrator',
          speaker_id: 4,
          speaker_state: 'certain',
          speaker_evidence: { rule: 'narrative_default', score: 0.99 },
          confidence: {
            speaker: 0.95,
          },
        },
        {
          segment_id: '101-003',
          chapter_id: 2,
          segment_index: 1,
          original_text: 'Unknown breathes deep and says nothing.',
          speaker: 'unknown',
          speaker_id: null,
          speaker_state: 'certain',
          speaker_evidence: { rule: 'pronoun_no_match', score: 0.41 },
          confidence: {
            speaker: 0.98,
          },
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

function renderSpeakerReviewPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/review/speakers',
        element: <ProjectSpeakerReviewPage />,
      },
      {
        path: '/projects/:project_id/export',
        element: <div data-testid="export-page">Export page</div>,
      },
    ],
    { initialEntries: ['/projects/101/review/speakers'] },
  );

  render(<RouterProvider router={router} />);
}

describe('project speaker review page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 101,
      projectTitle: 'Arcane Project',
      selectedMode: null,
      chapterCount: 4,
      runId: 77,
    });
  });

  it('renders low-confidence speaker rows by default and supports filtering', async () => {
    const user = userEvent.setup();
    renderSpeakerReviewPage();

    expect(screen.getByTestId('output-probabilistic-disclaimer')).toBeInTheDocument();
    expect(screen.getByText(/AI outputs are probabilistic, not perfect/i)).toBeInTheDocument();

    expect(screen.getByTestId('speaker-review-candidates')).toHaveTextContent('Review candidates: 2');
    expect(screen.getByTestId('speaker-review-total')).toHaveTextContent('Total segments: 3');

    expect(screen.getByText('101-001')).toBeInTheDocument();
    expect(screen.getByText('101-003')).toBeInTheDocument();
    expect(screen.queryByText('101-002')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Show all segments' }));
    expect(screen.getByText('101-002')).toBeInTheDocument();
  });

  it('tracks local review actions and can continue to export', async () => {
    const user = userEvent.setup();
    renderSpeakerReviewPage();

    await user.click(screen.getByTestId('speaker-review-toggle-101-001'));
    expect(screen.getByTestId('reviewed-count')).toHaveTextContent('Reviewed: 1');
    expect(screen.getByRole('button', { name: 'Reviewed' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Continue to Export/i }));
    expect(screen.getByTestId('export-page')).toBeInTheDocument();
  });
});
