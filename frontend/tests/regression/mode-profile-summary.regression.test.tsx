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
