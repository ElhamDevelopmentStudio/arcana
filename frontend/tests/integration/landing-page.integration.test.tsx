import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const createProjectDraftTrigger = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useHealthQuery: () => ({ data: { status: 'ok' } }),
  useModeCatalogQuery: () => ({
    data: {
      modes: ['audiobook', 'academic', 'author', 'custom'],
      default_mode: 'audiobook',
      persisted_in: ['projects.selected_mode', 'runs.config_json.mode'],
      mode_profiles: {
        audiobook: {
          max_segment_chars: 120,
          export_formats: ['json', 'csv', 'time_series_json', 'graph_json'],
          export_chunk_size: 500,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          llm_confidence_threshold: 0.6,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          deep_semantic_refinement: false,
          deterministic_mode: false,
          contradiction_review_required: true,
          web_scraping_enabled: false,
          profile_intent: 'tts-ready segmentation and stable narration defaults',
        },
        academic: {
          max_segment_chars: 220,
          export_formats: ['json', 'csv'],
          export_chunk_size: 500,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          llm_confidence_threshold: 0.6,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          deep_semantic_refinement: false,
          deterministic_mode: false,
          contradiction_review_required: true,
          web_scraping_enabled: false,
          profile_intent: 'longer analytical segments for metric-friendly aggregation',
        },
        author: {
          max_segment_chars: 160,
          export_formats: ['json'],
          export_chunk_size: 500,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          llm_confidence_threshold: 0.6,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          deep_semantic_refinement: false,
          deterministic_mode: false,
          contradiction_review_required: true,
          web_scraping_enabled: false,
          profile_intent: 'balanced segmentation for narrative-health diagnostics',
        },
        custom: {
          max_segment_chars: 255,
          export_formats: ['json'],
          export_chunk_size: 500,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          llm_confidence_threshold: 0.6,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          deep_semantic_refinement: false,
          deterministic_mode: false,
          contradiction_review_required: true,
          web_scraping_enabled: false,
          profile_intent: 'user-tuned baseline with conservative defaults',
        },
      },
    },
  }),
  useProjectControlPanelSummaryQuery: () => ({
    data: {
      schema_version: '1.0.0',
      output_schema: 'project_control_panel_summary_json',
      output_format: 'json',
      output_id: 'CP-001',
      output_name: 'project_control_panel_summary',
      generated_at: '2026-02-27T00:00:00Z',
      generated_by: 'build_project_control_panel_summary',
      total_projects: 6,
      project_counts_by_state: [
        { lifecycle_state: 'draft', project_count: 2 },
        { lifecycle_state: 'ingested', project_count: 1 },
        { lifecycle_state: 'configured', project_count: 1 },
        { lifecycle_state: 'running', project_count: 0 },
        { lifecycle_state: 'completed', project_count: 1 },
        { lifecycle_state: 'failed', project_count: 1 },
        { lifecycle_state: 'archived', project_count: 0 },
      ],
      active_run_count: 1,
      blocked_export_project_count: 2,
      blocked_export_run_count: 1,
      recent_failure_count: 1,
      recent_failures: [],
    },
  }),
  useCreateProjectDraftMutation: () => ({
    isMutating: false,
    trigger: createProjectDraftTrigger,
  }),
}));

import { LandingPage } from '@/pages/landing/landing-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

function renderLandingPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <LandingPage />,
      },
      {
        path: '/dashboard',
        element: <div data-testid="dashboard-page">Dashboard</div>,
      },
      {
        path: '/projects/new',
        element: <div data-testid="project-new-page">Project New</div>,
      },
    ],
    { initialEntries: ['/'] },
  );
  render(<RouterProvider router={router} />);
}

describe('landing page integration', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    createProjectDraftTrigger.mockReset();
    createProjectDraftTrigger.mockResolvedValue({
      id: 333,
      title: 'Landing Draft',
      selected_mode: 'audiobook',
      selected_modes: ['audiobook'],
      llm_enabled: false,
      do_not_store_source_text: false,
      configuration_snapshot_id: 'project-333-config-initial',
      character_map_finalized: false,
      ingestion_timestamp: null,
      created_at: '2026-02-27T00:00:00Z',
    });
  });

  it('renders live summary stats and navigates to dashboard', async () => {
    const user = userEvent.setup();
    renderLandingPage();

    expect(screen.getByText('Service status:')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();

    await user.click(screen.getByTestId('landing-enter-dashboard'));

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
  });

  it('creates draft project from landing dialog and routes to project new flow', async () => {
    const user = userEvent.setup();
    renderLandingPage();

    await user.click(screen.getByTestId('landing-create-draft'));
    await user.type(screen.getByTestId('landing-create-project-input'), 'Landing Draft');
    await user.click(screen.getByTestId('landing-create-project-submit'));

    await waitFor(() => {
      expect(createProjectDraftTrigger).toHaveBeenCalledTimes(1);
    });
    expect(createProjectDraftTrigger).toHaveBeenCalledWith({
      title: 'Landing Draft',
      do_not_store_source_text: false,
    });

    await waitFor(() => {
      expect(screen.getByTestId('project-new-page')).toBeInTheDocument();
    });
  });
});

