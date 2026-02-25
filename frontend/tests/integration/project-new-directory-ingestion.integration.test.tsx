import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const createProjectTrigger = vi.fn();
const ingestTxtTrigger = vi.fn();
const ingestDirectoryTrigger = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useCreateProjectMutation: () => ({
    isMutating: false,
    trigger: createProjectTrigger,
  }),
  useIngestTxtMutation: () => ({
    isMutating: false,
    trigger: ingestTxtTrigger,
  }),
  useIngestChapterDirectoryMutation: () => ({
    isMutating: false,
    trigger: ingestDirectoryTrigger,
  }),
}));

import { ProjectNewPage } from '@/pages/projects/project-new-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

function renderProjectNewPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/new',
        element: <ProjectNewPage />,
      },
      {
        path: '/projects/:project_id/mode',
        element: <div data-testid="mode-page">Mode page</div>,
      },
    ],
    { initialEntries: ['/projects/new'] },
  );
  render(<RouterProvider router={router} />);
}

describe('project new page directory ingestion', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    createProjectTrigger.mockReset();
    ingestTxtTrigger.mockReset();
    ingestDirectoryTrigger.mockReset();
    createProjectTrigger.mockResolvedValue({
      id: 101,
      title: 'Shadow Slave PoC',
      selected_mode: 'audiobook',
      selected_modes: ['audiobook'],
      configuration_snapshot_id: 'project-101-config-initial',
      ingestion_timestamp: null,
      created_at: '2026-02-25T00:00:00Z',
    });
    ingestDirectoryTrigger.mockResolvedValue({
      project_id: 101,
      chapter_count: 2,
    });
  });

  it('uses chapter-directory ingestion mutation when source type is directory', async () => {
    const user = userEvent.setup();
    renderProjectNewPage();

    await user.click(screen.getByTestId('create-project-button'));

    await user.selectOptions(screen.getByTestId('ingestion-source-select'), 'directory');

    const chapterOne = new File(['First chapter'], 'chapter_1.txt', { type: 'text/plain' });
    const chapterTwo = new File(['Second chapter'], 'chapter_2.txt', { type: 'text/plain' });
    await user.upload(screen.getByTestId('directory-upload-input'), [chapterOne, chapterTwo]);

    await user.click(screen.getByTestId('upload-txt-button'));

    expect(ingestDirectoryTrigger).toHaveBeenCalledTimes(1);
    expect(ingestDirectoryTrigger).toHaveBeenCalledWith({
      files: [chapterOne, chapterTwo],
    });
    expect(screen.getByTestId('chapter-count-state')).toHaveTextContent('Detected chapters: 2');
  });
});
