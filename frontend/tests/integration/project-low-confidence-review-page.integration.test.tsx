import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectLowConfidenceReviewPage } from '@/pages/projects/project-low-confidence-review-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useExportPayloadQuery: () => ({
    data: {
      project_id: 303,
      project_title: 'Shaded Ledger',
      run_id: 101,
      status: 'complete',
      segments: [
        {
          segment_id: '303-001',
          chapter_id: 1,
          original_text: 'Calm winds rolled over still water.',
          type: 'narration',
          confidence: { speaker: 0.91, emotion: 0.9 },
          speaker: 'Narrator',
          speaker_state: 'certain',
          emotion_state: 'certain',
          type_confidence: 0.96,
          type_state: 'certain',
          emotion_evidence: { signal: 'non-strong emotional content' },
          speaker_evidence: { rule: 'narrative_default' },
          tension_contribution: {
            state: 'certain',
            confidence: 0.99,
          },
          dominance_contribution: {
            state: 'certain',
            confidence: 0.92,
          },
          summary_tag: {
            state: 'certain',
            confidence: 0.88,
          },
          tag_states: {
            type: 'certain',
            speaker: 'certain',
            emotion: 'certain',
            tension: 'certain',
            dominance: 'certain',
            summary: 'certain',
          },
        },
        {
          segment_id: '303-002',
          chapter_id: 1,
          original_text: 'He muttered uncertainly about the dark corridor.',
          type: 'narration',
          confidence: { speaker: 0.62, emotion: 0.74 },
          speaker: 'Kai',
          speaker_state: 'uncertain',
          emotion_state: 'uncertain',
          type_confidence: 0.91,
          type_state: 'certain',
          emotion_evidence: { signal: 'weak emotional cue' },
          speaker_evidence: { rule: 'ambiguous_prefix' },
          tension_contribution: {
            state: 'certain',
            confidence: 0.4,
          },
          dominance_contribution: {
            state: 'certain',
            confidence: 0.95,
          },
          summary_tag: {
            state: 'uncertain',
            confidence: 0.93,
          },
          tag_states: {
            type: 'certain',
            speaker: 'uncertain',
            emotion: 'certain',
            tension: 'certain',
            dominance: 'certain',
            summary: 'certain',
          },
        },
        {
          segment_id: '303-003',
          chapter_id: 2,
          original_text: 'A hard edge of fear cut through the silence.',
          type: 'narration',
          confidence: { speaker: 0.93, emotion: 0.82 },
          speaker: 'unknown',
          speaker_state: 'certain',
          emotion_state: 'certain',
          type_confidence: 0.81,
          type_state: 'certain',
          emotion_evidence: { signal: 'emotion words' },
          speaker_evidence: { rule: 'none' },
          tension_contribution: {
            state: 'uncertain',
            confidence: 0.91,
          },
          dominance_contribution: {
            state: 'uncertain',
            confidence: 0.79,
          },
          summary_tag: {
            state: 'certain',
            confidence: 0.92,
          },
          tag_states: {
            type: 'certain',
            speaker: 'certain',
            emotion: 'certain',
            tension: 'uncertain',
            dominance: 'uncertain',
            summary: 'certain',
          },
        },
        {
          segment_id: '303-004',
          chapter_id: 2,
          original_text: 'She entered the hall and offered peace.',
          type: 'narration',
          confidence: { speaker: 0.95, emotion: 0.95 },
          speaker: 'Lina',
          speaker_state: 'certain',
          emotion_state: 'certain',
          type_confidence: 0.97,
          type_state: 'certain',
          emotion_evidence: { signal: 'stable tone' },
          speaker_evidence: { rule: 'speaker_prefix' },
          tension_contribution: {
            state: 'certain',
            confidence: 0.86,
          },
          dominance_contribution: {
            state: 'certain',
            confidence: 0.87,
          },
          summary_tag: {
            state: 'certain',
            confidence: 0.9,
          },
          tag_states: {
            type: 'certain',
            speaker: 'certain',
            emotion: 'certain',
            tension: 'certain',
            dominance: 'certain',
            summary: 'certain',
          },
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

function renderLowConfidenceReviewPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/review/low-confidence',
        element: <ProjectLowConfidenceReviewPage />,
      },
      {
        path: '/projects/:project_id/export',
        element: <div data-testid="export-page">Export page</div>,
      },
    ],
    { initialEntries: ['/projects/303/review/low-confidence'] },
  );

  render(<RouterProvider router={router} />);
}

describe('project low-confidence review page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 303,
      projectTitle: 'Shaded Ledger',
      selectedMode: null,
      chapterCount: 2,
      runId: 101,
    });
  });

  it('renders low-confidence review candidates by default and supports filtering', async () => {
    const user = userEvent.setup();
    renderLowConfidenceReviewPage();

    expect(screen.getByTestId('low-confidence-review-candidates')).toHaveTextContent('Review candidates: 2');
    expect(screen.getByTestId('low-confidence-review-total')).toHaveTextContent('Total segments: 4');

    expect(screen.getByText('303-002')).toBeInTheDocument();
    expect(screen.getByText('303-003')).toBeInTheDocument();
    expect(screen.queryByText('303-001')).not.toBeInTheDocument();
    expect(screen.queryByText('303-004')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Show all segments' }));
    expect(screen.getByText('303-001')).toBeInTheDocument();
    expect(screen.getByText('303-004')).toBeInTheDocument();
  });

  it('tracks local review actions and can continue to export', async () => {
    const user = userEvent.setup();
    renderLowConfidenceReviewPage();

    await user.click(screen.getByTestId('low-confidence-review-toggle-303-003'));
    expect(screen.getByTestId('low-confidence-review-reviewed')).toHaveTextContent('Reviewed: 1');
    expect(screen.getByRole('button', { name: 'Reviewed' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Continue to Export/i }));
    expect(screen.getByTestId('export-page')).toBeInTheDocument();
  });
});
