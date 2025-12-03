import { render, screen } from '@testing-library/react';
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
});
