import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectCharactersPage } from '@/pages/projects/project-characters-page';

const importTrigger = vi.fn();
const mutateCharacterMap = vi.fn();
const saveCharactersMutationTrigger = vi.fn();
const autoExtractCharactersMutationTrigger = vi.fn();
const scrapeCharactersMutationTrigger = vi.fn();
const mergeCharactersMutationTrigger = vi.fn();
const pronunciationPreviewMutationTrigger = vi.fn();
const finalizeCharactersMutationTrigger = vi.fn();
const characterMapQueryData = {
  project_id: 101,
  characters: [
    {
      name: 'Kai',
      verbalized_form: 'Kai',
      gender: 'male',
      aliases: ['K'],
      notes: 'Initial',
      source: 'import',
      confidence: 1.0,
    },
  ],
};

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useImportCharactersMutation: () => ({
    isMutating: false,
    trigger: importTrigger,
  }),
  useCharacterMapQuery: () => ({
    data: characterMapQueryData,
    isLoading: false,
    error: null,
    mutate: mutateCharacterMap,
  }),
  useSaveCharacterMapMutation: () => ({
    isMutating: false,
    trigger: saveCharactersMutationTrigger,
  }),
  useAutoExtractCharactersMutation: () => ({
    isMutating: false,
    trigger: autoExtractCharactersMutationTrigger,
  }),
  useScrapeCharactersMutation: () => ({
    isMutating: false,
    trigger: scrapeCharactersMutationTrigger,
  }),
  useMergeCharactersMutation: () => ({
    isMutating: false,
    trigger: mergeCharactersMutationTrigger,
  }),
  useFinalizeCharacterMapMutation: () => ({
    isMutating: false,
    trigger: finalizeCharactersMutationTrigger,
  }),
  usePronunciationPreviewMutation: () => ({
    isMutating: false,
    trigger: pronunciationPreviewMutationTrigger,
  }),
}));

function renderCharacterPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/characters',
        element: <ProjectCharactersPage />,
      },
      {
        path: '/projects/:project_id/pipeline-setup',
        element: <div data-testid="pipeline-page">Pipeline setup</div>,
      },
    ],
    { initialEntries: ['/projects/101/characters'] },
  );
  render(<RouterProvider router={router} />);
}

describe('project characters page manual editor', () => {
  beforeEach(() => {
    importTrigger.mockReset();
    mutateCharacterMap.mockReset();
    saveCharactersMutationTrigger.mockReset();
    autoExtractCharactersMutationTrigger.mockReset();
    scrapeCharactersMutationTrigger.mockReset();
    mergeCharactersMutationTrigger.mockReset();
    pronunciationPreviewMutationTrigger.mockReset();
    finalizeCharactersMutationTrigger.mockReset();
    saveCharactersMutationTrigger.mockResolvedValue({
      project_id: 101,
      characters: [
        {
          name: 'Lio',
          verbalized_form: 'Lee-o',
          gender: 'female',
          aliases: [],
          notes: null,
          source_trace: [],
          source: 'manual',
          confidence: 1.0,
        },
      ],
    });
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'Captain saw the Aegis at dawn.',
      after: 'Captain saw the EE-jis at dawn.',
      character_name: null,
      included_scopes: ['global'],
      replacements: [
        {
          term: 'Aegis',
          verbalized_form: 'EE-jis',
          count: 1,
          scope: 'global',
        },
      ],
    });
  });

  it('adds, removes, and saves manual character rows', async () => {
    const user = userEvent.setup();
    renderCharacterPage();

    expect(screen.getByTestId('character-list-state')).toHaveTextContent('1 row(s) loaded.');

    expect(screen.getByPlaceholderText('Character name')).toHaveValue('Kai');

    await user.click(screen.getByRole('button', { name: 'Add Row' }));

    const nameInputs = screen.getAllByPlaceholderText('Character name');
    const verbalizedInputs = screen.getAllByPlaceholderText('Verbalized form');
    expect(nameInputs).toHaveLength(2);

    await user.type(nameInputs[1], 'Lio');
    await user.type(verbalizedInputs[1], 'Lee-o');

    const selectFields = screen.getAllByRole('combobox');
    await user.selectOptions(selectFields[1], 'female');

    const removeButtons = screen.getAllByRole('button', { name: 'Remove' });
    await user.click(removeButtons[0]);

    expect(screen.getAllByPlaceholderText('Character name')).toHaveLength(1);

    await user.click(screen.getByTestId('character-map-save-button'));

    expect(saveCharactersMutationTrigger).toHaveBeenCalledTimes(1);
    expect(saveCharactersMutationTrigger).toHaveBeenCalledWith({
      characters: [
        {
          name: 'Lio',
          verbalized_form: 'Lee-o',
          gender: 'female',
          aliases: [],
          notes: null,
          source_trace: [],
          source: 'manual',
          confidence: 1.0,
        },
      ],
    });
  });

  it('displays canonical merge suggestions when merge endpoint returns them', async () => {
    const user = userEvent.setup();
    mergeCharactersMutationTrigger.mockResolvedValue({
      project_id: 101,
      status: 'complete',
      candidate_count: 2,
      proposed_characters: [
        {
          name: 'Mire',
          verbalized_form: 'Mire',
          gender: 'unknown',
          aliases: [],
          notes: null,
          source: 'auto',
          confidence: 0.6,
          source_trace: [],
        },
      ],
      candidates: [
        {
          name: 'Mira',
          verbalized_form: 'Mira',
          gender: 'female',
          aliases: [],
          notes: null,
          source: 'merged:auto|user_import',
          confidence: 1.0,
          source_trace: [],
        },
        {
          name: 'Mire',
          verbalized_form: 'Mire',
          gender: 'unknown',
          aliases: [],
          notes: null,
          source: 'auto',
          confidence: 0.6,
          source_trace: [],
        },
      ],
      canonical_merge_suggestions: [
        {
          canonical_name: 'Mira',
          alias_name: 'Mire',
          score: 0.8755,
          candidate_source: 'auto',
          canonical_source: 'user_import',
          reason: 'name_similarity',
        },
      ],
    });

    renderCharacterPage();

    await user.click(screen.getByRole('button', { name: 'Merge user + auto + scraped candidates' }));

    expect(mergeCharactersMutationTrigger).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('character-merged-state')).toHaveTextContent('Merged candidates: 2');
    expect(screen.getByTestId('character-merge-suggestions-state')).toHaveTextContent('1 suggestion(s).');
    expect(screen.getByTestId('character-proposed-state')).toHaveTextContent('1 proposed character(s) ready for review.');
    expect(screen.getByTestId('proposed-character-mire')).toBeInTheDocument();
    expect(screen.getByText('Mire → Mira')).toBeInTheDocument();
    expect(screen.getByText('Reason: name_similarity')).toBeInTheDocument();
  });

  it('allows approving and rejecting proposed characters', async () => {
    const user = userEvent.setup();
    mergeCharactersMutationTrigger.mockResolvedValue({
      project_id: 101,
      status: 'complete',
      candidate_count: 3,
      proposed_characters: [
        {
          name: 'Mire',
          verbalized_form: 'Mire',
          gender: 'unknown',
          aliases: [],
          notes: null,
          source: 'auto',
          confidence: 0.61,
          source_trace: [],
        },
        {
          name: 'Tao',
          verbalized_form: 'Tao',
          gender: 'female',
          aliases: [],
          notes: null,
          source: 'auto',
          confidence: 0.58,
          source_trace: [],
        },
      ],
      candidates: [
        {
          name: 'Mira',
          verbalized_form: 'Mira',
          gender: 'female',
          aliases: [],
          notes: null,
          source: 'merged:auto|user_import',
          confidence: 1.0,
          source_trace: [],
        },
        {
          name: 'Mire',
          verbalized_form: 'Mire',
          gender: 'unknown',
          aliases: [],
          notes: null,
          source: 'auto',
          confidence: 0.61,
          source_trace: [],
        },
        {
          name: 'Tao',
          verbalized_form: 'Tao',
          gender: 'female',
          aliases: [],
          notes: null,
          source: 'auto',
          confidence: 0.58,
          source_trace: [],
        },
      ],
      canonical_merge_suggestions: [],
    });
    renderCharacterPage();

    await user.click(screen.getByRole('button', { name: 'Merge user + auto + scraped candidates' }));

    expect(screen.getByTestId('character-proposed-state')).toHaveTextContent('2 proposed character(s) ready for review.');
    const mireRow = screen.getByTestId('proposed-character-mire');

    await user.click(within(mireRow).getByRole('button', { name: 'Approve' }));
    expect(screen.getAllByPlaceholderText('Character name').filter((input) => input.getAttribute('value') === 'Mire')).toHaveLength(1);

    await user.click(within(screen.getByTestId('proposed-character-tao')).getByRole('button', { name: 'Reject' }));
    expect(screen.getByTestId('character-proposed-state')).toHaveTextContent('No proposed characters to review.');
    expect(screen.queryByTestId('proposed-character-tao')).not.toBeInTheDocument();

    const manualNameInputs = screen.getAllByPlaceholderText('Character name');
    expect(manualNameInputs).toHaveLength(2);
    expect(screen.getAllByPlaceholderText('Character name').filter((input) => input.getAttribute('value') === 'Mire')).toHaveLength(1);
  });

  it('refreshes rows from backend state after import succeeds', async () => {
    const file = new File(['{}'], 'characters.json', { type: 'application/json' });
    importTrigger.mockResolvedValue({ project_id: 101, imported_count: 1 });
    const user = userEvent.setup();

    renderCharacterPage();
    await user.upload(screen.getByTestId('character-file-input'), file);
    await user.click(screen.getByTestId('character-import-button'));

    expect(importTrigger).toHaveBeenCalledTimes(1);
    expect(importTrigger).toHaveBeenCalledWith({ file });
    expect(mutateCharacterMap).toHaveBeenCalledTimes(1);
  });

  it('runs pronunciation preview and renders before/after substitutions', async () => {
    const user = userEvent.setup();
    renderCharacterPage();

    await user.type(screen.getByTestId('pronunciation-preview-text'), 'Captain saw the Aegis at dawn.');
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'Captain saw the Aegis at dawn.',
      case_sensitive: true,
      match_whole_words: true,
      alias_aware: false,
      include_global_scope: true,
      include_character_scope: false,
      include_place_scope: false,
      include_artifact_scope: false,
      include_invented_scope: false,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('Captain saw the Aegis at dawn.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('Captain saw the EE-jis at dawn.');
    expect(screen.getByText('Included scopes: global')).toBeInTheDocument();
    expect(screen.getByTestId('pronunciation-preview-replacements')).toHaveTextContent('Aegis → EE-jis');
  });

  it('runs pronunciation preview with place-name dictionary scope', async () => {
    const user = userEvent.setup();
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'They entered Narnia at dawn.',
      after: 'They entered Nar-nia at dawn.',
      character_name: null,
      included_scopes: ['place'],
      replacements: [
        {
          term: 'Narnia',
          verbalized_form: 'Nar-nia',
          count: 1,
          scope: 'place',
        },
      ],
    });

    renderCharacterPage();

    await user.click(screen.getByRole('checkbox', { name: 'Global pronunciation dictionary' }));
    await user.click(screen.getByRole('checkbox', { name: 'Place-name pronunciation dictionary' }));
    await user.type(screen.getByTestId('pronunciation-preview-text'), 'They entered Narnia at dawn.');
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'They entered Narnia at dawn.',
      case_sensitive: true,
      match_whole_words: true,
      alias_aware: false,
      include_global_scope: false,
      include_character_scope: false,
      include_place_scope: true,
      include_artifact_scope: false,
      include_invented_scope: false,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('They entered Narnia at dawn.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('They entered Nar-nia at dawn.');
    expect(screen.getByText('Included scopes: place')).toBeInTheDocument();
    expect(screen.getByTestId('pronunciation-preview-replacements')).toHaveTextContent('Narnia → Nar-nia');
  });

  it('renders pronunciation ambiguity warnings from the preview response', async () => {
    const user = userEvent.setup();
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'Aegis sounded.',
      after: 'Ah-jeez sounded.',
      character_name: 'Kai',
      included_scopes: ['global', 'character'],
      warnings: [
        {
          type: 'ambiguous_replacement',
          term: 'Aegis',
          message: "Ambiguous replacement for 'Aegis' from scopes: character, global.",
          scopes: ['character', 'global'],
          competing_verbalized_forms: ['Ah-jeez', 'EE-jis'],
        },
      ],
      replacements: [
        {
          term: 'Aegis',
          verbalized_form: 'Ah-jeez',
          count: 1,
          scope: 'character',
        },
      ],
    });

    renderCharacterPage();

    await user.click(screen.getByRole('checkbox', { name: 'Character-specific dictionary' }));
    await user.selectOptions(screen.getByLabelText('Character scope target'), 'Kai');
    await user.type(screen.getByTestId('pronunciation-preview-text'), 'Aegis sounded.');
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'Aegis sounded.',
      case_sensitive: true,
      match_whole_words: true,
      alias_aware: false,
      include_global_scope: true,
      include_character_scope: true,
      include_place_scope: false,
      include_artifact_scope: false,
      include_invented_scope: false,
      character_name: 'Kai',
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('Aegis sounded.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('Ah-jeez sounded.');
    expect(screen.getByTestId('pronunciation-preview-warnings')).toHaveTextContent(
      "Ambiguous replacement for 'Aegis' from scopes: character, global.",
    );
    expect(screen.getByTestId('pronunciation-preview-warnings')).toHaveTextContent(
      'Competing verbalized forms: Ah-jeez, EE-jis',
    );
    expect(screen.getByTestId('pronunciation-preview-warnings')).toHaveTextContent('Scopes: character, global');
  });

  it('switches whole-word matching mode for pronunciation preview', async () => {
    const user = userEvent.setup();
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'CaptainAegis and Aegis.',
      after: 'CaptainEE-jis and EE-jis.',
      character_name: null,
      included_scopes: ['global'],
      replacements: [
        {
          term: 'Aegis',
          verbalized_form: 'EE-jis',
          count: 2,
          scope: 'global',
        },
      ],
    });

    renderCharacterPage();

    await user.type(screen.getByTestId('pronunciation-preview-text'), 'CaptainAegis and Aegis.');
    await user.click(screen.getByRole('checkbox', { name: 'Match whole words only' }));
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'CaptainAegis and Aegis.',
      case_sensitive: true,
      match_whole_words: false,
      alias_aware: false,
      include_global_scope: true,
      include_character_scope: false,
      include_place_scope: false,
      include_artifact_scope: false,
      include_invented_scope: false,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('CaptainAegis and Aegis.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('CaptainEE-jis and EE-jis.');
  });

  it('switches case-sensitive matching mode for pronunciation preview', async () => {
    const user = userEvent.setup();
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'Aegis sailed with aegis and AEGIS in the hold.',
      after: 'EE-jis sailed with EE-jis and EE-jis in the hold.',
      character_name: null,
      included_scopes: ['global'],
      replacements: [
        {
          term: 'Aegis',
          verbalized_form: 'EE-jis',
          count: 3,
          scope: 'global',
        },
      ],
    });

    renderCharacterPage();

    await user.type(screen.getByTestId('pronunciation-preview-text'), 'Aegis sailed with aegis and AEGIS in the hold.');
    await user.click(screen.getByRole('checkbox', { name: 'Case-sensitive matching' }));
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'Aegis sailed with aegis and AEGIS in the hold.',
      case_sensitive: false,
      match_whole_words: true,
      alias_aware: false,
      include_global_scope: true,
      include_character_scope: false,
      include_place_scope: false,
      include_artifact_scope: false,
      include_invented_scope: false,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('Aegis sailed with aegis and AEGIS in the hold.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue(
      'EE-jis sailed with EE-jis and EE-jis in the hold.',
    );
  });

  it('enables alias-aware substitution mode for pronunciation preview', async () => {
    const user = userEvent.setup();
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'Al met Kai.',
      after: 'A-lise met Kai.',
      character_name: 'Alice',
      included_scopes: ['character'],
      replacements: [
        {
          term: 'Al',
          verbalized_form: 'A-lise',
          count: 1,
          scope: 'character',
        },
      ],
    });

    renderCharacterPage();

    await user.type(screen.getByTestId('pronunciation-preview-text'), 'Al met Kai.');
    await user.click(screen.getByRole('checkbox', { name: 'Global pronunciation dictionary' }));
    await user.click(screen.getByRole('checkbox', { name: 'Character-specific dictionary' }));
    await user.selectOptions(screen.getByLabelText('Character scope target'), 'Kai');
    await user.click(screen.getByRole('checkbox', { name: 'Alias-aware substitution' }));
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'Al met Kai.',
      case_sensitive: true,
      match_whole_words: true,
      alias_aware: true,
      include_global_scope: false,
      include_character_scope: true,
      include_place_scope: false,
      include_artifact_scope: false,
      include_invented_scope: false,
      character_name: 'Kai',
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('Al met Kai.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('A-lise met Kai.');
  });

  it('runs pronunciation preview with artifact terminology dictionary scope', async () => {
    const user = userEvent.setup();
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'The phylactery hummed nearby.',
      after: 'The artefact-phrase hummed nearby.',
      character_name: null,
      included_scopes: ['artifact'],
      replacements: [
        {
          term: 'phylactery',
          verbalized_form: 'artefact-phrase',
          count: 1,
          scope: 'artifact',
        },
      ],
    });

    renderCharacterPage();

    await user.click(screen.getByRole('checkbox', { name: 'Global pronunciation dictionary' }));
    await user.click(screen.getByRole('checkbox', { name: 'Artifact terminology dictionary' }));
    await user.type(screen.getByTestId('pronunciation-preview-text'), 'The phylactery hummed nearby.');
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'The phylactery hummed nearby.',
      case_sensitive: true,
      match_whole_words: true,
      alias_aware: false,
      include_global_scope: false,
      include_character_scope: false,
      include_place_scope: false,
      include_artifact_scope: true,
      include_invented_scope: false,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('The phylactery hummed nearby.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('The artefact-phrase hummed nearby.');
    expect(screen.getByText('Included scopes: artifact')).toBeInTheDocument();
    expect(screen.getByTestId('pronunciation-preview-replacements')).toHaveTextContent('phylactery → artefact-phrase');
  });

  it('runs pronunciation preview with invented word dictionary scope', async () => {
    const user = userEvent.setup();
    pronunciationPreviewMutationTrigger.mockResolvedValue({
      project_id: 101,
      before: 'A drakene rose slowly.',
      after: 'A dra-ke-n rose slowly.',
      character_name: null,
      included_scopes: ['invented'],
      replacements: [
        {
          term: 'drakene',
          verbalized_form: 'dra-ke-n',
          count: 1,
          scope: 'invented',
        },
      ],
    });

    renderCharacterPage();

    await user.click(screen.getByRole('checkbox', { name: 'Global pronunciation dictionary' }));
    await user.click(screen.getByRole('checkbox', { name: 'Invented word dictionary' }));
    await user.type(screen.getByTestId('pronunciation-preview-text'), 'A drakene rose slowly.');
    await user.click(screen.getByTestId('pronunciation-preview-button'));

    expect(pronunciationPreviewMutationTrigger).toHaveBeenCalledWith({
      text: 'A drakene rose slowly.',
      case_sensitive: true,
      match_whole_words: true,
      alias_aware: false,
      include_global_scope: false,
      include_character_scope: false,
      include_place_scope: false,
      include_artifact_scope: false,
      include_invented_scope: true,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('A drakene rose slowly.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('A dra-ke-n rose slowly.');
    expect(screen.getByText('Included scopes: invented')).toBeInTheDocument();
    expect(screen.getByTestId('pronunciation-preview-replacements')).toHaveTextContent('drakene → dra-ke-n');
  });
});
