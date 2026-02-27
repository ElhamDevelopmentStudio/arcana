import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectSetupPage } from '@/pages/projects/project-setup-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectSetupStatusQueryMock = vi.fn();
const useAppendChapterMutationMock = vi.fn();
const useAttachInitialIngestionSourceMutationMock = vi.fn();
const useIngestChapterDirectoryMutationMock = vi.fn();
const useIngestEpubMutationMock = vi.fn();
const useIngestMarkdownMutationMock = vi.fn();
const useIngestTxtMutationMock = vi.fn();
const useModeCatalogQueryMock = vi.fn();
const useSwitchModeMutationMock = vi.fn();
const setupStatusMutateMock = vi.fn();
const appendChapterTriggerMock = vi.fn();
const attachInitialIngestionSourceTriggerMock = vi.fn();
const ingestChapterDirectoryTriggerMock = vi.fn();
const ingestEpubTriggerMock = vi.fn();
const ingestMarkdownTriggerMock = vi.fn();
const ingestTxtTriggerMock = vi.fn();
const switchModeTriggerMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectSetupStatusQuery: (...args: Parameters<typeof useProjectSetupStatusQueryMock>) =>
    useProjectSetupStatusQueryMock(...args),
  useAppendChapterMutation: (...args: Parameters<typeof useAppendChapterMutationMock>) =>
    useAppendChapterMutationMock(...args),
  useAttachInitialIngestionSourceMutation: (...args: Parameters<typeof useAttachInitialIngestionSourceMutationMock>) =>
    useAttachInitialIngestionSourceMutationMock(...args),
  useIngestChapterDirectoryMutation: (...args: Parameters<typeof useIngestChapterDirectoryMutationMock>) =>
    useIngestChapterDirectoryMutationMock(...args),
  useIngestEpubMutation: (...args: Parameters<typeof useIngestEpubMutationMock>) =>
    useIngestEpubMutationMock(...args),
  useIngestMarkdownMutation: (...args: Parameters<typeof useIngestMarkdownMutationMock>) =>
    useIngestMarkdownMutationMock(...args),
  useIngestTxtMutation: (...args: Parameters<typeof useIngestTxtMutationMock>) => useIngestTxtMutationMock(...args),
  useModeCatalogQuery: (...args: Parameters<typeof useModeCatalogQueryMock>) => useModeCatalogQueryMock(...args),
  useSwitchModeMutation: (...args: Parameters<typeof useSwitchModeMutationMock>) => useSwitchModeMutationMock(...args),
}));

function renderProjectSetupPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/setup',
        element: <ProjectSetupPage />,
      },
      {
        path: '/projects/:project_id/overview',
        element: <div data-testid="project-overview-route">Project overview route</div>,
      },
      {
        path: '/projects/:project_id/characters',
        element: <div data-testid="project-characters-route">Project characters route</div>,
      },
      {
        path: '/projects/:project_id/pipeline-setup',
        element: <div data-testid="project-pipeline-setup-route">Project pipeline setup route</div>,
      },
    ],
    { initialEntries: ['/projects/77/setup'] },
  );

  render(<RouterProvider router={router} />);
  return router;
}

describe('project setup page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectSetupStatusQueryMock.mockReset();
    useAppendChapterMutationMock.mockReset();
    useAttachInitialIngestionSourceMutationMock.mockReset();
    useIngestChapterDirectoryMutationMock.mockReset();
    useIngestEpubMutationMock.mockReset();
    useIngestMarkdownMutationMock.mockReset();
    useIngestTxtMutationMock.mockReset();
    useModeCatalogQueryMock.mockReset();
    useSwitchModeMutationMock.mockReset();
    setupStatusMutateMock.mockReset();
    appendChapterTriggerMock.mockReset();
    attachInitialIngestionSourceTriggerMock.mockReset();
    ingestChapterDirectoryTriggerMock.mockReset();
    ingestEpubTriggerMock.mockReset();
    ingestMarkdownTriggerMock.mockReset();
    ingestTxtTriggerMock.mockReset();
    switchModeTriggerMock.mockReset();

    useAttachInitialIngestionSourceMutationMock.mockReturnValue({
      isMutating: false,
      trigger: attachInitialIngestionSourceTriggerMock,
    });
    useAppendChapterMutationMock.mockReturnValue({
      isMutating: false,
      trigger: appendChapterTriggerMock,
    });
    useIngestChapterDirectoryMutationMock.mockReturnValue({
      isMutating: false,
      trigger: ingestChapterDirectoryTriggerMock,
    });
    useIngestEpubMutationMock.mockReturnValue({
      isMutating: false,
      trigger: ingestEpubTriggerMock,
    });
    useIngestMarkdownMutationMock.mockReturnValue({
      isMutating: false,
      trigger: ingestMarkdownTriggerMock,
    });
    useIngestTxtMutationMock.mockReturnValue({
      isMutating: false,
      trigger: ingestTxtTriggerMock,
    });
    useModeCatalogQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      data: {
        modes: ['audiobook', 'academic', 'author', 'custom'],
        default_mode: 'audiobook',
      },
    });
    useSwitchModeMutationMock.mockReturnValue({
      isMutating: false,
      trigger: switchModeTriggerMock,
    });
  });

  it('renders loading state while setup status is pending', () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: true,
      data: undefined,
      error: undefined,
      mutate: setupStatusMutateMock,
    });

    renderProjectSetupPage();

    expect(screen.getByTestId('project-setup-loading')).toBeInTheDocument();
  });

  it('renders retryable setup-status error state', async () => {
    const user = userEvent.setup();
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      data: undefined,
      error: new Error('setup status failed'),
      mutate: setupStatusMutateMock,
    });

    renderProjectSetupPage();

    expect(screen.getByTestId('project-setup-error')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry setup status' }));
    expect(setupStatusMutateMock).toHaveBeenCalledTimes(1);
  });

  it('renders backend-driven setup checklist rows', () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'ingested',
        next_required_action: 'select_mode',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    expect(screen.getByTestId('project-setup-ready')).toBeInTheDocument();
    expect(screen.getByText('Setup in progress')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-step-ingestion')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-step-mode_selection')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-step-initial_run')).toBeInTheDocument();
    expect(screen.getByText('Mode Selection')).toBeInTheDocument();
  });

  it('renders character and voice readiness with explicit CTAs', async () => {
    const user = userEvent.setup();
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'configured',
        next_required_action: 'run',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: true, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: true, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    expect(screen.getByTestId('project-setup-character-voice-readiness')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-character-readiness')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-voice-readiness')).toBeInTheDocument();

    await user.click(screen.getByTestId('project-setup-go-characters'));
    expect(await screen.findByTestId('project-characters-route')).toBeInTheDocument();
  });

  it('navigates to pipeline setup from voice readiness CTA', async () => {
    const user = userEvent.setup();
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'configured',
        next_required_action: 'run',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: true, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    await user.click(screen.getByTestId('project-setup-go-pipeline-setup'));
    expect(await screen.findByTestId('project-pipeline-setup-route')).toBeInTheDocument();
  });

  it('attaches first-source metadata from setup source form', async () => {
    const user = userEvent.setup();
    attachInitialIngestionSourceTriggerMock.mockResolvedValue({
      project_id: 77,
      source: 'markdown',
      source_filename: 'novel.md',
      attached_at: '2026-02-27T00:00:00Z',
    });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'draft',
        next_required_action: 'ingest',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    await user.selectOptions(screen.getByTestId('project-setup-source-type-select'), 'markdown');
    await user.clear(screen.getByTestId('project-setup-source-filename-input'));
    await user.type(screen.getByTestId('project-setup-source-filename-input'), 'novel.md');
    await user.click(screen.getByTestId('project-setup-source-attach-submit'));

    expect(attachInitialIngestionSourceTriggerMock).toHaveBeenCalledWith({
      source: 'markdown',
      source_filename: 'novel.md',
    });
    expect(ingestTxtTriggerMock).not.toHaveBeenCalled();
    expect(setupStatusMutateMock).toHaveBeenCalled();
  });

  it('submits txt ingestion from setup ingestion form', async () => {
    const user = userEvent.setup();
    ingestTxtTriggerMock.mockResolvedValue({
      project_id: 77,
      chapter_count: 12,
      warnings: [
        {
          type: 'duplicate_title',
          message: 'Duplicate chapter title detected: Chapter 1',
        },
      ],
      normalization_report: {
        chapter_count: 12,
        suspected_duplicate_title_count: 1,
        suspected_duplicate_content_count: 0,
        encoding_issue_count: 0,
      },
    });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'draft',
        next_required_action: 'ingest',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    const txtFile = new File(['chapter one'], 'novel.txt', { type: 'text/plain' });
    const input = screen.getByTestId('project-setup-ingestion-file-input');
    await user.upload(input, txtFile);
    await user.click(screen.getByTestId('project-setup-ingestion-submit'));

    expect(attachInitialIngestionSourceTriggerMock).not.toHaveBeenCalled();
    expect(ingestTxtTriggerMock).toHaveBeenCalledWith({ file: txtFile });
    expect(setupStatusMutateMock).toHaveBeenCalled();
    expect(screen.getByTestId('project-setup-ingestion-output-summary')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-ingestion-output-source')).toHaveTextContent('TXT');
    expect(screen.getByTestId('project-setup-ingestion-output-warning-count')).toHaveTextContent('Warnings: 1');
    expect(screen.getByTestId('project-setup-normalization-summary-duplicate-title-count')).toHaveTextContent(
      'Duplicate titles: 1',
    );
    expect(screen.getByTestId('project-setup-ingestion-warning-list')).toHaveTextContent(
      'Duplicate chapter title detected: Chapter 1',
    );
  });

  it('submits markdown ingestion from setup markdown form', async () => {
    const user = userEvent.setup();
    ingestMarkdownTriggerMock.mockResolvedValue({
      project_id: 77,
      chapter_count: 7,
    });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'draft',
        next_required_action: 'ingest',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    const markdownFile = new File(['# Chapter one'], 'novel.md', { type: 'text/markdown' });
    const input = screen.getByTestId('project-setup-markdown-ingestion-file-input');
    await user.upload(input, markdownFile);
    await user.click(screen.getByTestId('project-setup-markdown-ingestion-submit'));

    expect(ingestTxtTriggerMock).not.toHaveBeenCalled();
    expect(ingestMarkdownTriggerMock).toHaveBeenCalledWith({ file: markdownFile });
    expect(setupStatusMutateMock).toHaveBeenCalled();
  });

  it('submits epub ingestion from setup epub form', async () => {
    const user = userEvent.setup();
    ingestEpubTriggerMock.mockResolvedValue({
      project_id: 77,
      chapter_count: 4,
    });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'draft',
        next_required_action: 'ingest',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    const epubFile = new File(['epub bytes'], 'novel.epub', { type: 'application/epub+zip' });
    const input = screen.getByTestId('project-setup-epub-ingestion-file-input');
    await user.upload(input, epubFile);
    await user.click(screen.getByTestId('project-setup-epub-ingestion-submit'));

    expect(ingestTxtTriggerMock).not.toHaveBeenCalled();
    expect(ingestMarkdownTriggerMock).not.toHaveBeenCalled();
    expect(ingestEpubTriggerMock).toHaveBeenCalledWith({ file: epubFile });
    expect(setupStatusMutateMock).toHaveBeenCalled();
  });

  it('submits chapter-directory ingestion from setup chapter-files form', async () => {
    const user = userEvent.setup();
    ingestChapterDirectoryTriggerMock.mockResolvedValue({
      project_id: 77,
      chapter_count: 9,
    });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'draft',
        next_required_action: 'ingest',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    const firstChapter = new File(['chapter 1'], '01.txt', { type: 'text/plain' });
    const secondChapter = new File(['chapter 2'], '02.txt', { type: 'text/plain' });
    const input = screen.getByTestId('project-setup-chapters-dir-ingestion-files-input');
    await user.upload(input, [firstChapter, secondChapter]);
    await user.click(screen.getByTestId('project-setup-chapters-dir-ingestion-submit'));

    expect(ingestTxtTriggerMock).not.toHaveBeenCalled();
    expect(ingestMarkdownTriggerMock).not.toHaveBeenCalled();
    expect(ingestEpubTriggerMock).not.toHaveBeenCalled();
    expect(ingestChapterDirectoryTriggerMock).toHaveBeenCalledWith({ files: [firstChapter, secondChapter] });
    expect(setupStatusMutateMock).toHaveBeenCalled();
  });

  it('submits append-chapter ingestion from setup append form', async () => {
    const user = userEvent.setup();
    appendChapterTriggerMock.mockResolvedValue({
      project_id: 77,
      chapter_count: 10,
    });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'ingested',
        next_required_action: 'select_mode',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    const chapterFile = new File(['extra chapter'], 'bonus-chapter.txt', { type: 'text/plain' });
    const input = screen.getByTestId('project-setup-append-chapter-file-input');
    await user.upload(input, chapterFile);
    await user.click(screen.getByTestId('project-setup-append-chapter-submit'));

    expect(ingestTxtTriggerMock).not.toHaveBeenCalled();
    expect(ingestMarkdownTriggerMock).not.toHaveBeenCalled();
    expect(ingestEpubTriggerMock).not.toHaveBeenCalled();
    expect(ingestChapterDirectoryTriggerMock).not.toHaveBeenCalled();
    expect(appendChapterTriggerMock).toHaveBeenCalledWith({ file: chapterFile });
    expect(setupStatusMutateMock).toHaveBeenCalled();
  });

  it('surfaces unsupported-file ingestion failures and allows retry', async () => {
    const user = userEvent.setup();
    ingestMarkdownTriggerMock
      .mockRejectedValueOnce(new Error('Only .md/.markdown files are supported'))
      .mockResolvedValueOnce({
        project_id: 77,
        chapter_count: 7,
      });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'draft',
        next_required_action: 'ingest',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    const markdownFile = new File(['bad extension'], 'bad.txt', { type: 'text/plain' });
    await user.upload(screen.getByTestId('project-setup-markdown-ingestion-file-input'), markdownFile);
    await user.click(screen.getByTestId('project-setup-markdown-ingestion-submit'));

    expect(screen.getByTestId('project-setup-ingestion-error-panel')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-ingestion-error-kind')).toHaveTextContent('unsupported_file');
    expect(screen.getByTestId('project-setup-ingestion-retry-button')).toHaveTextContent('Retry markdown ingestion');

    await user.click(screen.getByTestId('project-setup-ingestion-retry-button'));
    expect(ingestMarkdownTriggerMock).toHaveBeenCalledTimes(2);
    expect(setupStatusMutateMock).toHaveBeenCalledTimes(1);
  });

  it('surfaces overlap-conflict failures for append-chapter ingestion', async () => {
    const user = userEvent.setup();
    appendChapterTriggerMock.mockRejectedValue(new Error('409 overlap conflict: chapter overlaps existing ranges'));
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'ingested',
        next_required_action: 'select_mode',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    const chapterFile = new File(['overlap chapter'], 'overlap.txt', { type: 'text/plain' });
    await user.upload(screen.getByTestId('project-setup-append-chapter-file-input'), chapterFile);
    await user.click(screen.getByTestId('project-setup-append-chapter-submit'));

    expect(screen.getByTestId('project-setup-ingestion-error-panel')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-ingestion-error-kind')).toHaveTextContent('overlap_conflict');
  });

  it('surfaces validation failures for source attach requests', async () => {
    const user = userEvent.setup();
    attachInitialIngestionSourceTriggerMock.mockRejectedValue(new Error('Validation error: source filename is invalid.'));
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'draft',
        next_required_action: 'ingest',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    await user.selectOptions(screen.getByTestId('project-setup-source-type-select'), 'txt');
    await user.clear(screen.getByTestId('project-setup-source-filename-input'));
    await user.type(screen.getByTestId('project-setup-source-filename-input'), 'novel?.txt');
    await user.click(screen.getByTestId('project-setup-source-attach-submit'));

    expect(screen.getByTestId('project-setup-ingestion-error-panel')).toBeInTheDocument();
    expect(screen.getByTestId('project-setup-ingestion-error-kind')).toHaveTextContent('validation_error');
    expect(screen.getByTestId('project-setup-ingestion-retry-button')).toHaveTextContent('Retry source attach');
  });

  it('applies mode selection from setup step and refreshes setup status', async () => {
    const user = userEvent.setup();
    switchModeTriggerMock.mockResolvedValue({
      project_id: 77,
      previous_mode: 'audiobook',
      selected_mode: 'author',
      selected_modes: ['author'],
      chapter_count: 12,
      reused_ingested_corpus: true,
      stale_runs_marked: 0,
    });
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'ingested',
        next_required_action: 'select_mode',
        is_complete: false,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    renderProjectSetupPage();

    await user.selectOptions(screen.getByTestId('project-setup-mode-select'), 'author');
    await user.click(screen.getByTestId('project-setup-mode-submit'));
    expect(screen.getByTestId('project-setup-mode-switch-confirm-dialog')).toBeInTheDocument();
    expect(switchModeTriggerMock).not.toHaveBeenCalled();
    await user.click(screen.getByTestId('project-setup-mode-switch-confirm-submit'));

    expect(switchModeTriggerMock).toHaveBeenCalledWith({ mode: 'author' });
    expect(setupStatusMutateMock).toHaveBeenCalled();
  });

  it('polls setup status while setup remains incomplete', async () => {
    vi.useFakeTimers();
    try {
      useProjectSetupStatusQueryMock.mockReturnValue({
        isLoading: false,
        error: undefined,
        mutate: setupStatusMutateMock,
        data: {
          project_id: 77,
          lifecycle_state: 'draft',
          next_required_action: 'ingest',
          is_complete: false,
          steps: [
            { step_id: 'ingestion', label: 'Ingestion', ready: false, required: true },
            { step_id: 'mode_selection', label: 'Mode Selection', ready: false, required: true },
            { step_id: 'initial_run', label: 'Initial Run', ready: false, required: true },
            { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
            { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
          ],
        },
      });

      renderProjectSetupPage();
      await vi.advanceTimersByTimeAsync(3_000);

      expect(setupStatusMutateMock).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('redirects to project overview when setup is complete', async () => {
    useProjectSetupStatusQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      mutate: setupStatusMutateMock,
      data: {
        project_id: 77,
        lifecycle_state: 'configured',
        next_required_action: 'run',
        is_complete: true,
        steps: [
          { step_id: 'ingestion', label: 'Ingestion', ready: true, required: true },
          { step_id: 'mode_selection', label: 'Mode Selection', ready: true, required: true },
          { step_id: 'initial_run', label: 'Initial Run', ready: true, required: true },
          { step_id: 'character_mapping', label: 'Character Mapping', ready: false, required: false },
          { step_id: 'voice_mapping', label: 'Voice Mapping', ready: false, required: false },
        ],
      },
    });

    const router = renderProjectSetupPage();

    expect(await screen.findByTestId('project-overview-route')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects/77/overview');
  });
});
