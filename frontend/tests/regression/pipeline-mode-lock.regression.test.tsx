import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useCharacterMapQuery: () => ({
    data: {
      project_id: 101,
      characters: [],
      character_map_finalized: true,
    },
  }),
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
          llm_confidence_threshold: 0.6,
          deep_semantic_refinement: false,
          deterministic_mode: false,
          profile_intent: 'tts-ready segmentation and stable narration defaults',
        },
      },
    },
  }),
  useSaveVoicesMutation: () => ({
    isMutating: false,
    trigger: vi.fn(),
  }),
  useRunPipelineMutation: () => ({
    isMutating: false,
    trigger: vi.fn(),
  }),
}));

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectPipelineSetupPage } from '@/pages/projects/project-pipeline-setup-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

function renderPipelinePage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/pipeline-setup',
        element: <ProjectPipelineSetupPage />,
      },
    ],
    { initialEntries: ['/projects/101/pipeline-setup'] },
  );

  render(<RouterProvider router={router} />);
}

describe('pipeline run mode lock regression', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 101,
      projectTitle: 'Shadow Slave',
      chapterCount: 12,
      runId: null,
      selectedMode: null,
    });
  });

  it('disables run action and shows lock hint when mode is not explicitly selected', () => {
    renderPipelinePage();

    expect(screen.getByTestId('run-pipeline-button')).toBeDisabled();
    expect(screen.getByTestId('mode-lock-hint')).toBeInTheDocument();
  });

  it('enables run action after explicit mode selection exists in workspace state', () => {
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    expect(screen.queryByTestId('mode-lock-hint')).not.toBeInTheDocument();
    expect(screen.getByTestId('run-pipeline-button')).toBeEnabled();
  });
});
