import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const createProjectTrigger = vi.fn();
const ingestTxtTrigger = vi.fn();
const ingestDirectoryTrigger = vi.fn();
const ingestMarkdownTrigger = vi.fn();
const ingestEpubTrigger = vi.fn();
const appendChapterTrigger = vi.fn();

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
  useIngestMarkdownMutation: () => ({
    isMutating: false,
    trigger: ingestMarkdownTrigger,
  }),
  useIngestEpubMutation: () => ({
    isMutating: false,
    trigger: ingestEpubTrigger,
  }),
  useAppendChapterMutation: () => ({
    isMutating: false,
    trigger: appendChapterTrigger,
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
    ingestMarkdownTrigger.mockReset();
    ingestEpubTrigger.mockReset();
    appendChapterTrigger.mockReset();
    createProjectTrigger.mockResolvedValue({
      id: 101,
      title: 'Shadow Slave PoC',
      selected_mode: 'audiobook',
      selected_modes: ['audiobook'],
      configuration_snapshot_id: 'project-101-config-initial',
      ingestion_timestamp: null,
      created_at: '2026-02-25T00:00:00Z',
    });
    ingestTxtTrigger.mockResolvedValue({
      project_id: 101,
      chapter_count: 2,
    });
    ingestDirectoryTrigger.mockResolvedValue({
      project_id: 101,
      chapter_count: 2,
    });
    ingestMarkdownTrigger.mockResolvedValue({
      project_id: 101,
      chapter_count: 2,
    });
    ingestEpubTrigger.mockResolvedValue({
      project_id: 101,
      chapter_count: 2,
    });
    appendChapterTrigger.mockResolvedValue({
      project_id: 101,
      chapter_count: 3,
    });
  });

  it('defaults to user-upload TXT ingestion path', async () => {
    const user = userEvent.setup();
    renderProjectNewPage();

    await user.click(screen.getByTestId('create-project-button'));

    expect(screen.getByTestId('ingestion-source-select')).toHaveValue('txt');
    const txtFile = new File(['chapter one'], 'novel.txt', { type: 'text/plain' });
    await user.upload(screen.getByTestId('txt-upload-input'), txtFile);

    await user.click(screen.getByTestId('upload-txt-button'));

    expect(ingestTxtTrigger).toHaveBeenCalledTimes(1);
    expect(ingestTxtTrigger).toHaveBeenCalledWith({ file: txtFile });
    expect(screen.getByTestId('chapter-count-state')).toHaveTextContent('Detected chapters: 2');
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

  it('uses markdown ingestion mutation when source type is markdown', async () => {
    const user = userEvent.setup();
    renderProjectNewPage();

    await user.click(screen.getByTestId('create-project-button'));

    await user.selectOptions(screen.getByTestId('ingestion-source-select'), 'markdown');

    const markdownFile = new File(['# Shadow Slave\n\n## Chapter 1\nSome content'], 'novel.md', { type: 'text/markdown' });
    await user.upload(screen.getByTestId('markdown-upload-input'), markdownFile);

    await user.click(screen.getByTestId('upload-txt-button'));

    expect(ingestMarkdownTrigger).toHaveBeenCalledTimes(1);
    expect(ingestMarkdownTrigger).toHaveBeenCalledWith({ file: markdownFile });
    expect(screen.getByTestId('chapter-count-state')).toHaveTextContent('Detected chapters: 2');
  });

  it('uses epub ingestion mutation when source type is epub', async () => {
    const user = userEvent.setup();
    renderProjectNewPage();

    await user.click(screen.getByTestId('create-project-button'));

    await user.selectOptions(screen.getByTestId('ingestion-source-select'), 'epub');

    const epubFile = new File(['epub payload'], 'novel.epub', { type: 'application/epub+zip' });
    await user.upload(screen.getByTestId('epub-upload-input'), epubFile);

    await user.click(screen.getByTestId('upload-txt-button'));

    expect(ingestEpubTrigger).toHaveBeenCalledTimes(1);
    expect(ingestEpubTrigger).toHaveBeenCalledWith({ file: epubFile });
    expect(screen.getByTestId('chapter-count-state')).toHaveTextContent('Detected chapters: 2');
  });

  it('uses append chapter mutation for incremental chapter ingestion', async () => {
    const user = userEvent.setup();
    renderProjectNewPage();

    await user.click(screen.getByTestId('create-project-button'));

    const appendFile = new File(['Bonus chapter content'], 'chapter_3.txt', { type: 'text/plain' });
    await user.upload(screen.getByTestId('append-chapter-upload-input'), appendFile);

    await user.click(screen.getByTestId('append-chapter-button'));

    expect(appendChapterTrigger).toHaveBeenCalledTimes(1);
    expect(appendChapterTrigger).toHaveBeenCalledWith({ file: appendFile });
    expect(screen.getByTestId('chapter-count-state')).toHaveTextContent('Detected chapters: 3');
  });
});
