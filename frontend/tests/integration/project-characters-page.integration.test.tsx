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
      match_whole_words: true,
      include_global_scope: true,
      include_character_scope: false,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('Captain saw the Aegis at dawn.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('Captain saw the EE-jis at dawn.');
    expect(screen.getByText('Included scopes: global')).toBeInTheDocument();
    expect(screen.getByTestId('pronunciation-preview-replacements')).toHaveTextContent('Aegis → EE-jis');
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
      match_whole_words: false,
      include_global_scope: true,
      include_character_scope: false,
    });
    expect(screen.getByTestId('pronunciation-preview-before')).toHaveValue('CaptainAegis and Aegis.');
    expect(screen.getByTestId('pronunciation-preview-after')).toHaveValue('CaptainEE-jis and EE-jis.');
  });
});
