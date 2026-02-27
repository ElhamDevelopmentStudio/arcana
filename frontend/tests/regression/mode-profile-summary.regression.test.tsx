import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useModeCatalogQuery: () => ({
    data: {
      modes: ['audiobook', 'academic', 'author', 'custom'],
      default_mode: 'audiobook',
      persisted_in: ['projects.selected_mode', 'runs.config_json.mode'],
      mode_profiles: {
        audiobook: {
          max_segment_chars: 120,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          web_scraping_enabled: false,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          profile_intent: 'tts-ready segmentation and stable narration defaults',
        },
        academic: {
          max_segment_chars: 220,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          web_scraping_enabled: false,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          profile_intent: 'longer analytical segments for metric-friendly aggregation',
        },
        author: {
          max_segment_chars: 160,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          web_scraping_enabled: false,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          profile_intent: 'balanced segmentation for narrative-health diagnostics',
        },
        custom: {
          max_segment_chars: 255,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          web_scraping_enabled: false,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          profile_intent: 'user-tuned baseline with conservative defaults',
        },
      },
    },
    isLoading: false,
    error: null,
  }),
  useProjectSetupStatusQuery: () => ({
    data: {
      project_id: 101,
      lifecycle_state: 'ingested',
      next_required_action: 'select_mode',
      is_complete: false,
      steps: [
        { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
        { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
        { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
      ],
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
    ],
    { initialEntries: ['/projects/101/mode'] },
  );
  render(<RouterProvider router={router} />);
}

describe('mode profile summary regression', () => {
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

  it('renders default mode profile summary from catalog when no explicit selection exists', () => {
    renderModePage();

    const summary = screen.getByTestId('mode-profile-summary');
    expect(summary).toHaveTextContent('Default max segment chars: 120');
    expect(summary).toHaveTextContent('Default provider: openrouter');
    expect(summary).toHaveTextContent('Default daily call cap: 25');
  });
});
