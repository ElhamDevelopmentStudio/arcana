import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectEmotionReviewPage } from '@/pages/projects/project-emotion-review-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useExportPayloadQuery: () => ({
    data: {
      project_id: 202,
      project_title: 'Arcane Mood Project',
      run_id: 88,
      status: 'complete',
      segments: [
        {
          segment_id: '202-001',
          chapter_id: 1,
          original_text: 'The dawn broke quietly over the quiet harbor.',
          emotion_valence: 0.02,
          emotion_intensity: 0.02,
          emotion_primary_label: 'neutral',
          emotion_secondary_label: 'neutral',
          emotion_confidence: 0.95,
          emotion_state: 'certain',
          emotion_evidence: { signal: 'stable narrative tone' },
          emotion_shift: { has_shift: false, state: 'certain', confidence: 0.5, evidence: { shift_count: 0 } },
        },
        {
          segment_id: '202-002',
          chapter_id: 1,
          original_text: 'Joy and laughter filled the morning hall.',
          emotion_valence: 0.72,
          emotion_intensity: 0.72,
          emotion_primary_label: 'positive',
          emotion_secondary_label: 'joyful',
          emotion_confidence: 0.91,
          emotion_state: 'certain',
          emotion_evidence: { signal: 'joyful language' },
          emotion_shift: { has_shift: false, state: 'certain', confidence: 0.4, evidence: { shift_count: 1 } },
        },
        {
          segment_id: '202-003',
          chapter_id: 1,
          original_text: 'A cold fear settled over the room before the ambush.',
          emotion_valence: -0.81,
          emotion_intensity: 0.81,
          emotion_primary_label: 'negative',
          emotion_secondary_label: 'fearful',
          emotion_confidence: 0.93,
          emotion_state: 'certain',
          emotion_evidence: { signal: 'fear cues' },
          emotion_shift: { has_shift: true, state: 'uncertain', confidence: 0.7, evidence: { shift_count: 2 } },
        },
        {
          segment_id: '202-004',
          chapter_id: 2,
          original_text: 'He stared ahead and waited for orders.',
          emotion_valence: -0.08,
          emotion_intensity: 0.08,
          emotion_primary_label: 'neutral',
          emotion_secondary_label: 'neutral',
          emotion_confidence: 0.3,
          emotion_state: 'uncertain',
          emotion_evidence: { signal: 'short and neutral' },
          emotion_shift: { has_shift: false, state: 'uncertain', confidence: 0.2, evidence: { shift_count: 0 } },
        },
        {
          segment_id: '202-005',
          chapter_id: 2,
          original_text: 'They charged forward as torches collapsed to ash.',
          emotion_valence: 0.22,
          emotion_intensity: 0.22,
          emotion_primary_label: 'negative',
          emotion_secondary_label: 'tense',
          emotion_confidence: 0.96,
          emotion_state: 'certain',
          emotion_evidence: { signal: 'mixed intensity' },
          emotion_shift: { has_shift: false, state: 'certain', confidence: 0.5, evidence: { shift_count: 0 } },
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

function renderEmotionReviewPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/review/emotions',
        element: <ProjectEmotionReviewPage />,
      },
      {
        path: '/projects/:project_id/export',
        element: <div data-testid="export-page">Export page</div>,
      },
    ],
    { initialEntries: ['/projects/202/review/emotions'] },
  );

  render(<RouterProvider router={router} />);
}

describe('project emotion review page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 202,
      projectTitle: 'Arcane Mood Project',
      selectedMode: null,
      chapterCount: 3,
      runId: 88,
    });
  });

  it('renders emotional peak/trough rows by default and supports filtering', async () => {
    const user = userEvent.setup();
    renderEmotionReviewPage();

    expect(screen.getByTestId('emotion-review-candidates')).toHaveTextContent('Review candidates: 3');
    expect(screen.getByTestId('emotion-review-total')).toHaveTextContent('Total segments: 5');

    expect(screen.getByText('202-002')).toBeInTheDocument();
    expect(screen.getByText('202-003')).toBeInTheDocument();
    expect(screen.getByText('202-004')).toBeInTheDocument();
    expect(screen.queryByText('202-001')).not.toBeInTheDocument();
    expect(screen.queryByText('202-005')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Show all segments' }));
    expect(screen.getByText('202-001')).toBeInTheDocument();
    expect(screen.getByText('202-005')).toBeInTheDocument();
  });

  it('tracks local review actions and can continue to export', async () => {
    const user = userEvent.setup();
    renderEmotionReviewPage();

    await user.click(screen.getByTestId('emotion-review-toggle-202-002'));
    expect(screen.getByTestId('emotion-review-reviewed')).toHaveTextContent('Reviewed: 1');
    expect(screen.getByRole('button', { name: 'Reviewed' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Continue to Export/i }));
    expect(screen.getByTestId('export-page')).toBeInTheDocument();
  });
});
