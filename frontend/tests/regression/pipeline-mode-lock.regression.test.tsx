import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const saveVoicesMutationTrigger = vi.fn();
const runPipelineMutationTrigger = vi.fn();

let characterMapQueryData = {
  project_id: 101,
  characters: [
    { name: 'Kai', verbalized_form: 'Kai', gender: 'male', voice_id: 'custom_kai', source: 'manual', confidence: 1.0 },
    { name: 'Lio', verbalized_form: 'Lio', gender: 'female', voice_id: null, source: 'manual', confidence: 1.0 },
    { name: 'Nox', verbalized_form: 'Nox', gender: 'unknown', voice_id: null, source: 'manual', confidence: 1.0 },
  ],
  character_map_finalized: true,
};
const modeCatalogData = {
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
          contradiction_review_required: true,
          web_scraping_enabled: false,
          speaker_confidence_threshold: 0.6,
          high_ambiguity_dialogue_flag_threshold: 2,
          unstable_emotion_shift_transition_threshold: 4,
          unstable_emotion_shift_density_threshold: 0.5,
          deep_semantic_refinement: false,
          deterministic_mode: false,
          profile_intent: 'tts-ready segmentation and stable narration defaults',
        },
      },
};

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useCharacterMapQuery: () => ({ data: characterMapQueryData }),
  useModeCatalogQuery: () => ({ data: modeCatalogData }),
  useSaveVoicesMutation: () => ({
    isMutating: false,
    trigger: saveVoicesMutationTrigger,
  }),
  useRunPipelineMutation: () => ({
    isMutating: false,
    trigger: runPipelineMutationTrigger,
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
    characterMapQueryData = {
      project_id: 101,
      characters: [
        { name: 'Kai', verbalized_form: 'Kai', gender: 'male', voice_id: 'custom_kai', source: 'manual', confidence: 1.0 },
        { name: 'Lio', verbalized_form: 'Lio', gender: 'female', voice_id: null, source: 'manual', confidence: 1.0 },
        { name: 'Nox', verbalized_form: 'Nox', gender: 'unknown', voice_id: null, source: 'manual', confidence: 1.0 },
      ],
      character_map_finalized: true,
    };
    saveVoicesMutationTrigger.mockReset();
    saveVoicesMutationTrigger.mockResolvedValue({
      project_id: 101,
      voice_config: {
        narrator_voice: 'narrator_default',
        male_default_voice: 'male_default',
        female_default_voice: 'female_default',
        neutral_default_voice: 'neutral_default',
        unknown_default_voice: 'unknown_default',
        internal_thought_voice_policy: 'character',
      },
    });
    runPipelineMutationTrigger.mockReset();
    runPipelineMutationTrigger.mockResolvedValue({
      run_id: 901,
      project_id: 101,
      status: 'completed',
      segment_count: 12,
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

  it('shows voice fallback preview with character-level and narrator fallback resolution', () => {
    renderPipelinePage();

    const previewTable = screen.getByTestId('voice-mapping-preview-table');

    expect(within(previewTable).getByText('Narrator')).toBeInTheDocument();
    expect(within(previewTable).getByText('narrator_default')).toBeInTheDocument();
    expect(within(previewTable).getByText('custom_kai')).toBeInTheDocument();
    expect(within(previewTable).getByText('female_default')).toBeInTheDocument();
    expect(within(previewTable).getByText('unknown_default')).toBeInTheDocument();
    expect(screen.getByTestId('internal-thought-preview')).toHaveTextContent('narrator_default');
  });

  it('updates fallback previews when defaults and thought policy change', async () => {
    const user = userEvent.setup();
    renderPipelinePage();

    const narratorInput = screen.getByLabelText('Narrator voice');
    const maleInput = screen.getByLabelText('Default male voice');
    const thoughtPolicy = screen.getByLabelText('Internal thought voice policy');
    const thoughtInput = screen.getByLabelText('Thought voice');

    await user.clear(narratorInput);
    await user.type(narratorInput, 'narrator_custom');
    await user.clear(maleInput);
    await user.type(maleInput, 'male_custom');
    await user.selectOptions(thoughtPolicy, 'thought_voice');
    await user.type(thoughtInput, 'thought_custom');

    expect(screen.getByTestId('voice-mapping-preview-table')).toHaveTextContent('narrator_custom');
    expect(screen.getByTestId('voice-mapping-preview-table')).toHaveTextContent('female_default');
    expect(screen.getByTestId('voice-mapping-preview-table')).toHaveTextContent('custom_kai');
    expect(screen.getByTestId('internal-thought-preview')).toHaveTextContent('thought_custom');
  });

  it('saves voice configuration payload through the voice editor form', async () => {
    const user = userEvent.setup();
    renderPipelinePage();

    await user.clear(screen.getByLabelText('Narrator voice'));
    await user.type(screen.getByLabelText('Narrator voice'), 'narrator_custom');
    await user.clear(screen.getByLabelText('Default male voice'));
    await user.type(screen.getByLabelText('Default male voice'), 'male_custom');
    await user.clear(screen.getByLabelText('Default female voice'));
    await user.type(screen.getByLabelText('Default female voice'), 'female_custom');
    await user.clear(screen.getByLabelText('Default neutral voice'));
    await user.type(screen.getByLabelText('Default neutral voice'), 'neutral_custom');
    await user.clear(screen.getByLabelText('Default unknown voice'));
    await user.type(screen.getByLabelText('Default unknown voice'), 'unknown_custom');
    await user.selectOptions(screen.getByLabelText('Internal thought voice policy'), 'thought_voice');
    await user.type(screen.getByLabelText('Thought voice'), 'thought_custom');

    await user.click(screen.getByRole('button', { name: 'Save Voice Config' }));

    expect(saveVoicesMutationTrigger).toHaveBeenCalledTimes(1);
    expect(saveVoicesMutationTrigger).toHaveBeenCalledWith({
      narrator_voice: 'narrator_custom',
      male_default_voice: 'male_custom',
      female_default_voice: 'female_custom',
      neutral_default_voice: 'neutral_custom',
      unknown_default_voice: 'unknown_custom',
      internal_thought_voice_policy: 'thought_voice',
      internal_thought_voice: 'thought_custom',
    });
  });

  it('posts expanded emotion taxonomy when selected', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    const emotionTaxonomySelect = screen.getByLabelText('Emotion taxonomy');
    await user.selectOptions(emotionTaxonomySelect, 'expanded');
    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({ emotion_taxonomy: 'expanded' }),
    );
  });

  it('defaults to basic emotion taxonomy in run payload', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({ emotion_taxonomy: 'basic' }),
    );
  });

  it('defaults contradiction review required to mode profile value in run payload', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({ contradiction_review_required: true }),
    );
  });

  it('allows users to disable contradiction review gate', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    const contradictionToggle = screen
      .getByText('Review contradictions before export')
      .closest('label')
      ?.querySelector('[role=\"switch\"]');
    expect(contradictionToggle).not.toBeNull();
    if (contradictionToggle) {
      await user.click(contradictionToggle as Element);
    }

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({ contradiction_review_required: false }),
    );
  });

  it('defaults warning threshold run fields to mode profile values', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({
        speaker_confidence_threshold: 0.6,
        high_ambiguity_dialogue_flag_threshold: 2,
        unstable_emotion_shift_transition_threshold: 4,
        unstable_emotion_shift_density_threshold: 0.5,
      }),
    );
  });

  it('defaults run payload export formats from selected mode profile', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({
        export_formats: ['json', 'csv', 'time_series_json', 'graph_json'],
      }),
    );
  });

  it('defaults run payload export chunk size from selected mode profile', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({
        export_chunk_size: 500,
      }),
    );
  });

  it('sends deterministic toggle fields when deterministic mode is enabled', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    const deterministicToggle = screen
      .getByText('Enable deterministic mode')
      .closest('label')
      ?.querySelector('[role="switch"]');
    expect(deterministicToggle).not.toBeNull();
    if (deterministicToggle) {
      await user.click(deterministicToggle as Element);
    }

    await user.type(screen.getByLabelText('Deterministic model identifier'), 'openai/gpt-4o-mini');
    await user.clear(screen.getByLabelText('Deterministic seed'));
    await user.type(screen.getByLabelText('Deterministic seed'), '2026');
    await user.clear(screen.getByLabelText('Randomization strategy'));
    await user.type(screen.getByLabelText('Randomization strategy'), 'custom-stable');

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({
        deterministic_mode: true,
        deterministic_model_identifier: 'openai/gpt-4o-mini',
        deterministic_seed: 2026,
        randomization_config: {
          seed: 2026,
          strategy: 'custom-stable',
          shuffle_enabled: false,
        },
      }),
    );
  });

  it('allows users to disable export formats in run payload', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    const graphJsonToggle = screen.getByLabelText('graph_json');
    await user.click(graphJsonToggle);
    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({
        export_formats: ['json', 'csv', 'time_series_json'],
      }),
    );
  });

  it('sends user-adjusted warning thresholds in run payload', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    await user.clear(screen.getByLabelText('Speaker confidence threshold'));
    await user.type(screen.getByLabelText('Speaker confidence threshold'), '0.55');
    await user.clear(screen.getByLabelText('High-ambiguity dialogue flag threshold'));
    await user.type(screen.getByLabelText('High-ambiguity dialogue flag threshold'), '7');
    await user.clear(screen.getByLabelText('Unstable emotion transition threshold'));
    await user.type(screen.getByLabelText('Unstable emotion transition threshold'), '9');
    await user.clear(screen.getByLabelText('Unstable emotion shift density threshold'));
    await user.type(screen.getByLabelText('Unstable emotion shift density threshold'), '0.23');

    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({
        speaker_confidence_threshold: 0.55,
        high_ambiguity_dialogue_flag_threshold: 7,
        unstable_emotion_shift_transition_threshold: 9,
        unstable_emotion_shift_density_threshold: 0.23,
      }),
    );
  });

  it('imports run preset json and uses imported values in run payload', async () => {
    const user = userEvent.setup();
    useWorkspaceStore.setState({ selectedMode: 'audiobook' });
    renderPipelinePage();

    const presetFile = new File(
      [
        JSON.stringify({
          run_config: {
            mode: 'audiobook',
            max_segment_chars: 175,
            llm_enabled: false,
            provider_name: 'openrouter',
            max_calls_per_day: 40,
            export_formats: ['json', 'csv'],
            deterministic_mode: true,
            deterministic_seed: 2026,
            config_schema_version: '0.9.0',
            legacy_profile_name: 'release-2025',
          },
        }),
      ],
      'run-preset.json',
      { type: 'application/json' },
    );

    await user.upload(screen.getByLabelText('Import run preset (.json)'), presetFile);
    await user.click(screen.getByTestId('run-pipeline-button'));

    expect(runPipelineMutationTrigger).toHaveBeenCalledTimes(1);
    expect(runPipelineMutationTrigger).toHaveBeenCalledWith(
      expect.objectContaining({
        max_segment_chars: 175,
        max_calls_per_day: 40,
        export_formats: ['json', 'csv'],
        deterministic_mode: true,
        deterministic_seed: 2026,
      }),
    );
    expect(runPipelineMutationTrigger.mock.calls[0][0]).not.toHaveProperty('config_schema_version');
    expect(runPipelineMutationTrigger.mock.calls[0][0]).not.toHaveProperty('legacy_profile_name');
  });
});
