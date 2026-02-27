import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectSetupPage } from '@/pages/projects/project-setup-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectSetupStatusQueryMock = vi.fn();
const useAttachInitialIngestionSourceMutationMock = vi.fn();
const useIngestTxtMutationMock = vi.fn();
const useModeCatalogQueryMock = vi.fn();
const useSwitchModeMutationMock = vi.fn();
const setupStatusMutateMock = vi.fn();
const attachInitialIngestionSourceTriggerMock = vi.fn();
const ingestTxtTriggerMock = vi.fn();
const switchModeTriggerMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectSetupStatusQuery: (...args: Parameters<typeof useProjectSetupStatusQueryMock>) =>
    useProjectSetupStatusQueryMock(...args),
  useAttachInitialIngestionSourceMutation: (...args: Parameters<typeof useAttachInitialIngestionSourceMutationMock>) =>
    useAttachInitialIngestionSourceMutationMock(...args),
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
    useAttachInitialIngestionSourceMutationMock.mockReset();
    useIngestTxtMutationMock.mockReset();
    useModeCatalogQueryMock.mockReset();
    useSwitchModeMutationMock.mockReset();
    setupStatusMutateMock.mockReset();
    attachInitialIngestionSourceTriggerMock.mockReset();
    ingestTxtTriggerMock.mockReset();
    switchModeTriggerMock.mockReset();

    useAttachInitialIngestionSourceMutationMock.mockReturnValue({
      isMutating: false,
      trigger: attachInitialIngestionSourceTriggerMock,
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

  it('attaches source and ingests txt from setup step form', async () => {
    const user = userEvent.setup();
    attachInitialIngestionSourceTriggerMock.mockResolvedValue({
      project_id: 77,
      source: 'txt',
      source_filename: 'novel.txt',
      attached_at: '2026-02-27T00:00:00Z',
    });
    ingestTxtTriggerMock.mockResolvedValue({
      project_id: 77,
      chapter_count: 12,
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

    expect(attachInitialIngestionSourceTriggerMock).toHaveBeenCalledWith({
      source: 'txt',
      source_filename: 'novel.txt',
    });
    expect(ingestTxtTriggerMock).toHaveBeenCalledWith({ file: txtFile });
    expect(setupStatusMutateMock).toHaveBeenCalled();
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
