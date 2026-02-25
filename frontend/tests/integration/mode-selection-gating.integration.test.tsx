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
      mode_profiles: {
        audiobook: {
          max_segment_chars: 120,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          profile_intent: 'tts-ready segmentation and stable narration defaults',
        },
        academic: {
          max_segment_chars: 220,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          profile_intent: 'longer analytical segments for metric-friendly aggregation',
        },
        author: {
          max_segment_chars: 160,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          profile_intent: 'balanced segmentation for narrative-health diagnostics',
        },
        custom: {
          max_segment_chars: 255,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          profile_intent: 'user-tuned baseline with conservative defaults',
        },
      },
    },
    isLoading: false,
    error: null,
  }),
  useRunDetailQuery: () => ({
    data: undefined,
    isLoading: false,
    error: null,
  }),
  useSwitchModeMutation: () => ({
    isMutating: false,
    trigger: async ({ mode }: { mode: string }) => ({
      project_id: 101,
      previous_mode: 'audiobook',
      selected_mode: mode,
      selected_modes: ['audiobook', mode],
      chapter_count: 12,
      reused_ingested_corpus: true,
      stale_runs_marked: 1,
    }),
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
    expect(screen.getByTestId('mode-profile-summary')).toHaveTextContent('Default max segment chars: 120');

    await user.selectOptions(screen.getByLabelText(/select mode/i), 'author');
    expect(continueButton).toBeEnabled();
    expect(screen.getByTestId('mode-profile-summary')).toHaveTextContent('Default max segment chars: 160');

    await user.click(continueButton);
    expect(screen.getByTestId('characters-page')).toBeInTheDocument();
  });
});
