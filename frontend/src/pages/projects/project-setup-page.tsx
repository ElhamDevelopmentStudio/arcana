import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import type { IngestResponseDto } from '@/app/schemas/api';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { ApiPanelError, ApiPanelLoading } from '@/components/ui/api-panel-state';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import {
  useAppendChapterMutation,
  useAttachInitialIngestionSourceMutation,
  useIngestChapterDirectoryMutation,
  useIngestEpubMutation,
  useIngestMarkdownMutation,
  useIngestTxtMutation,
  useModeCatalogQuery,
  useProjectSetupStatusQuery,
  useSwitchModeMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

const setupStatusPollIntervalMs = 3000;

type IngestionFailureKind = 'unsupported_file' | 'overlap_conflict' | 'validation_error' | 'unknown';

type IngestionFailureState = {
  kind: IngestionFailureKind;
  message: string;
  retryLabel: string;
};

type IngestionInsightState = {
  source: string;
  chapterCount: number;
  warningCount: number;
  warningMessages: string[];
  normalizationSummary: {
    chapterCount: number;
    duplicateTitleCount: number;
    duplicateContentCount: number;
    encodingIssueCount: number;
  };
};

function toStepStatusLabel(ready: boolean, required: boolean) {
  if (ready) {
    return required ? 'Complete' : 'Optional complete';
  }
  return required ? 'Required' : 'Optional';
}

function isAlreadyAttachedIngestionSourceError(error: unknown) {
  if (!(error instanceof Error)) {
    return false;
  }
  return error.message.toLowerCase().includes('already attached');
}

function classifyIngestionFailure(error: unknown): {
  kind: IngestionFailureKind;
  message: string;
} {
  const message = error instanceof Error ? error.message : 'Ingestion request failed.';
  const normalizedMessage = message.toLowerCase();

  if (normalizedMessage.includes('overlap')) {
    return { kind: 'overlap_conflict', message };
  }
  if (
    normalizedMessage.includes('unsupported') ||
    normalizedMessage.includes('only .') ||
    normalizedMessage.includes('file type') ||
    normalizedMessage.includes('content-type')
  ) {
    return { kind: 'unsupported_file', message };
  }
  if (
    normalizedMessage.includes('validation') ||
    normalizedMessage.includes('required') ||
    normalizedMessage.includes('invalid') ||
    normalizedMessage.includes('must')
  ) {
    return { kind: 'validation_error', message };
  }

  return { kind: 'unknown', message };
}

function toIngestionFailureHint(kind: IngestionFailureKind): string {
  if (kind === 'unsupported_file') {
    return 'Unsupported file type. Use the expected extension and retry.';
  }
  if (kind === 'overlap_conflict') {
    return 'Detected overlap conflict. Adjust chapter boundaries or file ordering, then retry.';
  }
  if (kind === 'validation_error') {
    return 'Validation failed. Correct the payload values and retry.';
  }
  return 'Ingestion failed. Retry the request or adjust inputs.';
}

function toNumericValue(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function toWarningMessages(warnings: Array<Record<string, unknown>>): string[] {
  return warnings.map((warning) => {
    const messageValue = warning.message;
    if (typeof messageValue === 'string' && messageValue.trim().length > 0) {
      return messageValue;
    }
    const detailValue = warning.detail;
    if (typeof detailValue === 'string' && detailValue.trim().length > 0) {
      return detailValue;
    }
    const typeValue = warning.type;
    if (typeof typeValue === 'string' && typeValue.trim().length > 0) {
      return typeValue;
    }
    try {
      return JSON.stringify(warning);
    } catch {
      return String(warning);
    }
  });
}

function buildIngestionInsight(source: string, response: IngestResponseDto): IngestionInsightState {
  const warnings = response.warnings ?? [];
  const normalizationReport = response.normalization_report ?? {};
  return {
    source,
    chapterCount: response.chapter_count,
    warningCount: warnings.length,
    warningMessages: toWarningMessages(warnings),
    normalizationSummary: {
      chapterCount: toNumericValue(normalizationReport.chapter_count),
      duplicateTitleCount: toNumericValue(normalizationReport.suspected_duplicate_title_count),
      duplicateContentCount: toNumericValue(normalizationReport.suspected_duplicate_content_count),
      encodingIssueCount: toNumericValue(normalizationReport.encoding_issue_count),
    },
  };
}

export function ProjectSetupPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const workspaceSelectedMode = useWorkspaceStore((state) => state.selectedMode);
  const setChapterCount = useWorkspaceStore((state) => state.setChapterCount);
  const setSelectedMode = useWorkspaceStore((state) => state.setSelectedMode);
  const projectId = routeProjectId ?? storeProjectId;
  const [ingestionFile, setIngestionFile] = useState<File | null>(null);
  const [markdownIngestionFile, setMarkdownIngestionFile] = useState<File | null>(null);
  const [epubIngestionFile, setEpubIngestionFile] = useState<File | null>(null);
  const [chapterDirectoryFiles, setChapterDirectoryFiles] = useState<File[]>([]);
  const [appendChapterFile, setAppendChapterFile] = useState<File | null>(null);
  const [ingestionSource, setIngestionSource] = useState<'txt' | 'markdown' | 'epub' | 'chapters-dir'>('txt');
  const [ingestionSourceFilename, setIngestionSourceFilename] = useState('');
  const [setupMode, setSetupMode] = useState<string | null>(workspaceSelectedMode);
  const [pendingSetupModeSwitch, setPendingSetupModeSwitch] = useState<string | null>(null);
  const [isModeSwitchConfirmOpen, setIsModeSwitchConfirmOpen] = useState(false);
  const [ingestionFailure, setIngestionFailure] = useState<IngestionFailureState | null>(null);
  const [isRetryingIngestion, setIsRetryingIngestion] = useState(false);
  const [lastIngestionInsight, setLastIngestionInsight] = useState<IngestionInsightState | null>(null);
  const retryIngestionRef = useRef<(() => Promise<void>) | null>(null);

  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const attachInitialIngestionSourceMutation = useAttachInitialIngestionSourceMutation(projectId);
  const appendChapterMutation = useAppendChapterMutation(projectId);
  const ingestChapterDirectoryMutation = useIngestChapterDirectoryMutation(projectId);
  const ingestTxtMutation = useIngestTxtMutation(projectId);
  const ingestMarkdownMutation = useIngestMarkdownMutation(projectId);
  const ingestEpubMutation = useIngestEpubMutation(projectId);
  const modeCatalogQuery = useModeCatalogQuery(projectId !== null);
  const switchModeMutation = useSwitchModeMutation(projectId);

  const setupErrorMessage =
    setupStatusQuery.error instanceof Error
      ? setupStatusQuery.error.message
      : 'Unable to load setup checklist.';
  const setupSteps = setupStatusQuery.data?.steps ?? [];
  const characterMappingStep = setupSteps.find((step) => step.step_id === 'character_mapping');
  const voiceMappingStep = setupSteps.find((step) => step.step_id === 'voice_mapping');
  const ingestionBusy = attachInitialIngestionSourceMutation.isMutating || ingestTxtMutation.isMutating;
  const markdownIngestionBusy = attachInitialIngestionSourceMutation.isMutating || ingestMarkdownMutation.isMutating;
  const epubIngestionBusy = attachInitialIngestionSourceMutation.isMutating || ingestEpubMutation.isMutating;
  const chapterDirectoryIngestionBusy =
    attachInitialIngestionSourceMutation.isMutating || ingestChapterDirectoryMutation.isMutating;
  const appendChapterBusy = attachInitialIngestionSourceMutation.isMutating || appendChapterMutation.isMutating;
  const sourceAttachBusy = attachInitialIngestionSourceMutation.isMutating;
  const modeOptions =
    modeCatalogQuery.data?.modes?.length !== undefined && modeCatalogQuery.data.modes.length > 0
      ? modeCatalogQuery.data.modes
      : ['audiobook', 'academic', 'author', 'custom'];
  const effectiveSetupMode = setupMode ?? workspaceSelectedMode ?? modeCatalogQuery.data?.default_mode ?? modeOptions[0] ?? '';
  const currentSetupMode =
    workspaceSelectedMode ?? modeCatalogQuery.data?.default_mode ?? modeOptions[0] ?? effectiveSetupMode;

  useEffect(() => {
    if (projectId === null || setupStatusQuery.isLoading || setupStatusQuery.error || setupStatusQuery.data === undefined) {
      return;
    }
    if (!setupStatusQuery.data.is_complete) {
      return;
    }
    navigate(`/projects/${projectId}/overview`, { replace: true });
  }, [
    navigate,
    projectId,
    setupStatusQuery.data,
    setupStatusQuery.error,
    setupStatusQuery.isLoading,
  ]);

  useEffect(() => {
    if (projectId === null || setupStatusQuery.error || setupStatusQuery.data === undefined) {
      return;
    }
    if (setupStatusQuery.data.is_complete) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void setupStatusQuery.mutate();
    }, setupStatusPollIntervalMs);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [projectId, setupStatusQuery.data, setupStatusQuery.error, setupStatusQuery.mutate]);

  useEffect(() => {
    if (setupMode !== null) {
      return;
    }
    if (!modeCatalogQuery.data?.default_mode) {
      return;
    }
    setSetupMode(modeCatalogQuery.data.default_mode);
  }, [modeCatalogQuery.data?.default_mode, setupMode]);

  useEffect(() => {
    if (ingestionFile === null) {
      return;
    }
    if (ingestionSource !== 'txt') {
      return;
    }
    if (ingestionSourceFilename.trim().length > 0) {
      return;
    }
    setIngestionSourceFilename(ingestionFile.name);
  }, [ingestionFile, ingestionSource, ingestionSourceFilename]);

  function clearIngestionFailure() {
    setIngestionFailure(null);
    retryIngestionRef.current = null;
  }

  function registerIngestionFailure(
    error: unknown,
    retryLabel: string,
    retryAction: () => Promise<void>,
  ) {
    const classified = classifyIngestionFailure(error);
    setIngestionFailure({
      kind: classified.kind,
      message: classified.message,
      retryLabel,
    });
    retryIngestionRef.current = retryAction;
    toast.error(classified.message);
  }

  async function retryLastIngestionFailure() {
    const retryAction = retryIngestionRef.current;
    if (!retryAction) {
      return;
    }
    setIsRetryingIngestion(true);
    try {
      await retryAction();
    } finally {
      setIsRetryingIngestion(false);
    }
  }

  async function handleAttachSourceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    const normalizedSourceFilename = ingestionSourceFilename.trim();
    if (!normalizedSourceFilename) {
      toast.error('Source filename is required.');
      return;
    }

    try {
      await attachInitialIngestionSourceMutation.trigger({
        source: ingestionSource,
        source_filename: normalizedSourceFilename,
      });
      clearIngestionFailure();
      toast.success('Source metadata attached.');
      await setupStatusQuery.mutate();
    } catch (error) {
      if (isAlreadyAttachedIngestionSourceError(error)) {
        clearIngestionFailure();
        toast.success('Source metadata already attached.');
        await setupStatusQuery.mutate();
        return;
      }
      const retrySource = ingestionSource;
      const retrySourceFilename = normalizedSourceFilename;
      registerIngestionFailure(error, 'Retry source attach', async () => {
        await attachInitialIngestionSourceMutation.trigger({
          source: retrySource,
          source_filename: retrySourceFilename,
        });
        clearIngestionFailure();
        toast.success('Source metadata attached.');
        await setupStatusQuery.mutate();
      });
    }
  }

  async function handleIngestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!ingestionFile) {
      toast.error('Choose a TXT file before ingestion.');
      return;
    }

    try {
      const response = await ingestTxtMutation.trigger({ file: ingestionFile });
      clearIngestionFailure();
      setLastIngestionInsight(buildIngestionInsight('TXT', response));
      setChapterCount(response.chapter_count);
      toast.success(`Ingestion complete: ${response.chapter_count} chapters detected.`);
      setIngestionFile(null);
      await setupStatusQuery.mutate();
    } catch (error) {
      const retryFile = ingestionFile;
      registerIngestionFailure(error, 'Retry TXT ingestion', async () => {
        const response = await ingestTxtMutation.trigger({ file: retryFile });
        clearIngestionFailure();
        setLastIngestionInsight(buildIngestionInsight('TXT', response));
        setChapterCount(response.chapter_count);
        toast.success(`Ingestion complete: ${response.chapter_count} chapters detected.`);
        setIngestionFile(null);
        await setupStatusQuery.mutate();
      });
    }
  }

  async function applySetupMode(nextMode: string) {
    try {
      const response = await switchModeMutation.trigger({ mode: nextMode });
      setSelectedMode(response.selected_mode);
      if (response.stale_runs_marked > 0) {
        toast.success(`Mode set to ${response.selected_mode}. ${response.stale_runs_marked} previous run(s) marked stale.`);
      } else {
        toast.success(`Mode set to ${response.selected_mode}.`);
      }
      await setupStatusQuery.mutate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Mode selection failed.');
    }
  }

  async function handleModeSelectionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!effectiveSetupMode) {
      toast.error('Select a mode before applying.');
      return;
    }
    if (effectiveSetupMode !== currentSetupMode) {
      setPendingSetupModeSwitch(effectiveSetupMode);
      setIsModeSwitchConfirmOpen(true);
      return;
    }

    await applySetupMode(effectiveSetupMode);
  }

  async function handleModeSwitchConfirmSubmit() {
    if (pendingSetupModeSwitch === null) {
      return;
    }
    await applySetupMode(pendingSetupModeSwitch);
    setPendingSetupModeSwitch(null);
    setIsModeSwitchConfirmOpen(false);
  }

  function handleModeSwitchConfirmOpenChange(nextOpen: boolean) {
    setIsModeSwitchConfirmOpen(nextOpen);
    if (!nextOpen && !switchModeMutation.isMutating) {
      setPendingSetupModeSwitch(null);
    }
  }

  async function handleEpubIngestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!epubIngestionFile) {
      toast.error('Choose an EPUB file before ingestion.');
      return;
    }

    try {
      const response = await ingestEpubMutation.trigger({ file: epubIngestionFile });
      clearIngestionFailure();
      setLastIngestionInsight(buildIngestionInsight('EPUB', response));
      setChapterCount(response.chapter_count);
      toast.success(`EPUB ingestion complete: ${response.chapter_count} chapters detected.`);
      setEpubIngestionFile(null);
      await setupStatusQuery.mutate();
    } catch (error) {
      const retryFile = epubIngestionFile;
      registerIngestionFailure(error, 'Retry EPUB ingestion', async () => {
        const response = await ingestEpubMutation.trigger({ file: retryFile });
        clearIngestionFailure();
        setLastIngestionInsight(buildIngestionInsight('EPUB', response));
        setChapterCount(response.chapter_count);
        toast.success(`EPUB ingestion complete: ${response.chapter_count} chapters detected.`);
        setEpubIngestionFile(null);
        await setupStatusQuery.mutate();
      });
    }
  }

  async function handleMarkdownIngestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!markdownIngestionFile) {
      toast.error('Choose a Markdown file before ingestion.');
      return;
    }

    try {
      const response = await ingestMarkdownMutation.trigger({ file: markdownIngestionFile });
      clearIngestionFailure();
      setLastIngestionInsight(buildIngestionInsight('Markdown', response));
      setChapterCount(response.chapter_count);
      toast.success(`Markdown ingestion complete: ${response.chapter_count} chapters detected.`);
      setMarkdownIngestionFile(null);
      await setupStatusQuery.mutate();
    } catch (error) {
      const retryFile = markdownIngestionFile;
      registerIngestionFailure(error, 'Retry markdown ingestion', async () => {
        const response = await ingestMarkdownMutation.trigger({ file: retryFile });
        clearIngestionFailure();
        setLastIngestionInsight(buildIngestionInsight('Markdown', response));
        setChapterCount(response.chapter_count);
        toast.success(`Markdown ingestion complete: ${response.chapter_count} chapters detected.`);
        setMarkdownIngestionFile(null);
        await setupStatusQuery.mutate();
      });
    }
  }

  async function handleChapterDirectoryIngestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (chapterDirectoryFiles.length === 0) {
      toast.error('Choose chapter files before ingestion.');
      return;
    }

    try {
      const response = await ingestChapterDirectoryMutation.trigger({ files: chapterDirectoryFiles });
      clearIngestionFailure();
      setLastIngestionInsight(buildIngestionInsight('Chapter Directory', response));
      setChapterCount(response.chapter_count);
      toast.success(`Chapter-directory ingestion complete: ${response.chapter_count} chapters detected.`);
      setChapterDirectoryFiles([]);
      await setupStatusQuery.mutate();
    } catch (error) {
      const retryFiles = [...chapterDirectoryFiles];
      registerIngestionFailure(error, 'Retry chapter-directory ingestion', async () => {
        const response = await ingestChapterDirectoryMutation.trigger({ files: retryFiles });
        clearIngestionFailure();
        setLastIngestionInsight(buildIngestionInsight('Chapter Directory', response));
        setChapterCount(response.chapter_count);
        toast.success(`Chapter-directory ingestion complete: ${response.chapter_count} chapters detected.`);
        setChapterDirectoryFiles([]);
        await setupStatusQuery.mutate();
      });
    }
  }

  async function handleAppendChapterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!appendChapterFile) {
      toast.error('Choose a chapter file before append.');
      return;
    }

    try {
      const response = await appendChapterMutation.trigger({ file: appendChapterFile });
      clearIngestionFailure();
      setLastIngestionInsight(buildIngestionInsight('Append Chapter', response));
      setChapterCount(response.chapter_count);
      toast.success(`Chapter appended: ${response.chapter_count} total chapters.`);
      setAppendChapterFile(null);
      await setupStatusQuery.mutate();
    } catch (error) {
      const retryFile = appendChapterFile;
      registerIngestionFailure(error, 'Retry append chapter', async () => {
        const response = await appendChapterMutation.trigger({ file: retryFile });
        clearIngestionFailure();
        setLastIngestionInsight(buildIngestionInsight('Append Chapter', response));
        setChapterCount(response.chapter_count);
        toast.success(`Chapter appended: ${response.chapter_count} total chapters.`);
        setAppendChapterFile(null);
        await setupStatusQuery.mutate();
      });
    }
  }

  return (
    <WorkflowPageShell
      description="Complete required project setup steps before full project workspace access."
      step="Setup"
      title="Project Setup Checklist"
    >
      {projectId === null ? (
        <Card data-testid="project-setup-project-required">
          <CardHeader>
            <CardTitle>Project required</CardTitle>
            <CardDescription>Select or create a project before opening setup.</CardDescription>
          </CardHeader>
        </Card>
      ) : setupStatusQuery.isLoading && setupStatusQuery.data === undefined ? (
        <div data-testid="project-setup-loading">
          <ApiPanelLoading description="Fetching setup-step readiness from backend." title="Loading setup checklist" />
        </div>
      ) : setupStatusQuery.error ? (
        <div data-testid="project-setup-error">
          <ApiPanelError
            description={setupErrorMessage}
            onRetry={() => {
              void setupStatusQuery.mutate();
            }}
            retryLabel="Retry setup status"
            title="Setup checklist unavailable"
          />
        </div>
      ) : (
        <div className="space-y-4" data-testid="project-setup-ready">
          <Card>
            <CardHeader className="space-y-2">
              <CardDescription>Project #{projectId}</CardDescription>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={setupStatusQuery.data?.is_complete ? 'default' : 'secondary'}>
                  {setupStatusQuery.data?.is_complete ? 'Setup complete' : 'Setup in progress'}
                </Badge>
                <Badge variant="outline">Lifecycle: {setupStatusQuery.data?.lifecycle_state ?? 'draft'}</Badge>
                <Badge variant="outline">Next action: {setupStatusQuery.data?.next_required_action ?? 'none'}</Badge>
                <Badge data-testid="project-setup-polling-indicator" variant="outline">
                  Polling every {setupStatusPollIntervalMs / 1000}s
                </Badge>
              </div>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>First-source attach + ingestion</CardTitle>
              <CardDescription>
                Attach initial source metadata (`POST /api/projects/:project_id/ingest/source`) and ingest TXT now.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {ingestionFailure ? (
                <div
                  className="mb-4 space-y-1 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2"
                  data-testid="project-setup-ingestion-error-panel"
                >
                  <p className="text-xs font-semibold text-destructive" data-testid="project-setup-ingestion-error-kind">
                    {ingestionFailure.kind}
                  </p>
                  <p className="text-xs text-destructive/90" data-testid="project-setup-ingestion-error-message">
                    {ingestionFailure.message}
                  </p>
                  <p className="text-xs text-muted-foreground">{toIngestionFailureHint(ingestionFailure.kind)}</p>
                  <div className="pt-1">
                    <Button
                      data-testid="project-setup-ingestion-retry-button"
                      disabled={isRetryingIngestion || retryIngestionRef.current === null}
                      onClick={() => {
                        void retryLastIngestionFailure();
                      }}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      {isRetryingIngestion ? 'Retrying...' : ingestionFailure.retryLabel}
                    </Button>
                  </div>
                </div>
              ) : null}
              {lastIngestionInsight ? (
                <div
                  className="mb-4 space-y-2 rounded-md border border-panel-border/70 bg-muted/35 px-3 py-2"
                  data-testid="project-setup-ingestion-output-summary"
                >
                  <p className="text-xs font-semibold text-foreground" data-testid="project-setup-ingestion-output-source">
                    Last ingestion source: {lastIngestionInsight.source}
                  </p>
                  <p className="text-xs text-muted-foreground" data-testid="project-setup-ingestion-output-chapter-count">
                    Chapters detected: {lastIngestionInsight.chapterCount}
                  </p>
                  <p className="text-xs text-muted-foreground" data-testid="project-setup-ingestion-output-warning-count">
                    Warnings: {lastIngestionInsight.warningCount}
                  </p>
                  <div className="grid gap-1 text-xs text-muted-foreground" data-testid="project-setup-normalization-summary">
                    <p>Normalization summary</p>
                    <p data-testid="project-setup-normalization-summary-chapter-count">
                      Reported chapters: {lastIngestionInsight.normalizationSummary.chapterCount}
                    </p>
                    <p data-testid="project-setup-normalization-summary-duplicate-title-count">
                      Duplicate titles: {lastIngestionInsight.normalizationSummary.duplicateTitleCount}
                    </p>
                    <p data-testid="project-setup-normalization-summary-duplicate-content-count">
                      Duplicate content: {lastIngestionInsight.normalizationSummary.duplicateContentCount}
                    </p>
                    <p data-testid="project-setup-normalization-summary-encoding-issue-count">
                      Encoding issues: {lastIngestionInsight.normalizationSummary.encodingIssueCount}
                    </p>
                  </div>
                  <div className="grid gap-1 text-xs text-muted-foreground">
                    <p>Warnings</p>
                    {lastIngestionInsight.warningMessages.length > 0 ? (
                      <ul className="list-disc pl-4" data-testid="project-setup-ingestion-warning-list">
                        {lastIngestionInsight.warningMessages.slice(0, 5).map((warningMessage) => (
                          <li key={warningMessage}>{warningMessage}</li>
                        ))}
                      </ul>
                    ) : (
                      <p data-testid="project-setup-ingestion-warning-empty">No warnings reported.</p>
                    )}
                  </div>
                </div>
              ) : null}
              <form className="grid gap-3" data-testid="project-setup-source-attach-form" onSubmit={handleAttachSourceSubmit}>
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-source-type">Source type</Label>
                  <NativeSelect
                    data-testid="project-setup-source-type-select"
                    disabled={sourceAttachBusy}
                    id="project-setup-source-type"
                    onChange={(event) => {
                      const source = event.target.value as 'txt' | 'markdown' | 'epub' | 'chapters-dir';
                      setIngestionSource(source);
                    }}
                    value={ingestionSource}
                  >
                    <option value="txt">txt</option>
                    <option value="markdown">markdown</option>
                    <option value="epub">epub</option>
                    <option value="chapters-dir">chapters-dir</option>
                  </NativeSelect>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-source-filename">Source filename</Label>
                  <Input
                    data-testid="project-setup-source-filename-input"
                    disabled={sourceAttachBusy}
                    id="project-setup-source-filename"
                    onChange={(event) => {
                      setIngestionSourceFilename(event.target.value);
                    }}
                    placeholder="novel.txt"
                    value={ingestionSourceFilename}
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">Attach source metadata before running ingestion endpoints.</p>
                  <Button data-testid="project-setup-source-attach-submit" disabled={sourceAttachBusy} type="submit">
                    {sourceAttachBusy ? 'Attaching source...' : 'Attach source metadata'}
                  </Button>
                </div>
              </form>

              <form
                className="mt-4 grid gap-3 border-t border-panel-border/70 pt-4"
                data-testid="project-setup-ingestion-form"
                onSubmit={handleIngestionSubmit}
              >
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-ingestion-file">TXT source file</Label>
                  <Input
                    accept=".txt,text/plain"
                    data-testid="project-setup-ingestion-file-input"
                    id="project-setup-ingestion-file"
                    onChange={(event) => {
                      const nextFile = event.target.files?.[0] ?? null;
                      setIngestionFile(nextFile);
                    }}
                    type="file"
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    TXT ingestion executes `POST /api/projects/:project_id/ingest/txt` after source metadata is attached.
                  </p>
                  <Button data-testid="project-setup-ingestion-submit" disabled={ingestionBusy} type="submit">
                    {ingestionBusy ? 'Ingesting...' : 'Ingest TXT'}
                  </Button>
                </div>
              </form>

              <form
                className="mt-4 grid gap-3 border-t border-panel-border/70 pt-4"
                data-testid="project-setup-markdown-ingestion-form"
                onSubmit={handleMarkdownIngestionSubmit}
              >
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-markdown-ingestion-file">Markdown source file</Label>
                  <Input
                    accept=".md,.markdown,text/markdown,text/plain"
                    data-testid="project-setup-markdown-ingestion-file-input"
                    id="project-setup-markdown-ingestion-file"
                    onChange={(event) => {
                      const nextFile = event.target.files?.[0] ?? null;
                      setMarkdownIngestionFile(nextFile);
                    }}
                    type="file"
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    Markdown ingestion executes `POST /api/projects/:project_id/ingest/markdown` after source metadata is attached.
                  </p>
                  <Button data-testid="project-setup-markdown-ingestion-submit" disabled={markdownIngestionBusy} type="submit">
                    {markdownIngestionBusy ? 'Ingesting markdown...' : 'Ingest Markdown'}
                  </Button>
                </div>
              </form>

              <form
                className="mt-4 grid gap-3 border-t border-panel-border/70 pt-4"
                data-testid="project-setup-epub-ingestion-form"
                onSubmit={handleEpubIngestionSubmit}
              >
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-epub-ingestion-file">EPUB source file</Label>
                  <Input
                    accept=".epub,application/epub+zip"
                    data-testid="project-setup-epub-ingestion-file-input"
                    id="project-setup-epub-ingestion-file"
                    onChange={(event) => {
                      const nextFile = event.target.files?.[0] ?? null;
                      setEpubIngestionFile(nextFile);
                    }}
                    type="file"
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    EPUB ingestion executes `POST /api/projects/:project_id/ingest/epub` after source metadata is attached.
                  </p>
                  <Button data-testid="project-setup-epub-ingestion-submit" disabled={epubIngestionBusy} type="submit">
                    {epubIngestionBusy ? 'Ingesting epub...' : 'Ingest EPUB'}
                  </Button>
                </div>
              </form>

              <form
                className="mt-4 grid gap-3 border-t border-panel-border/70 pt-4"
                data-testid="project-setup-chapters-dir-ingestion-form"
                onSubmit={handleChapterDirectoryIngestionSubmit}
              >
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-chapters-dir-ingestion-files">Chapter files (.txt)</Label>
                  <Input
                    accept=".txt,text/plain"
                    data-testid="project-setup-chapters-dir-ingestion-files-input"
                    id="project-setup-chapters-dir-ingestion-files"
                    multiple
                    onChange={(event) => {
                      setChapterDirectoryFiles(Array.from(event.target.files ?? []));
                    }}
                    type="file"
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    Chapter-directory ingestion executes `POST /api/projects/:project_id/ingest/chapters-dir` after source metadata is attached.
                  </p>
                  <Button
                    data-testid="project-setup-chapters-dir-ingestion-submit"
                    disabled={chapterDirectoryIngestionBusy}
                    type="submit"
                  >
                    {chapterDirectoryIngestionBusy ? 'Ingesting chapter files...' : 'Ingest Chapter Directory'}
                  </Button>
                </div>
              </form>

              <form
                className="mt-4 grid gap-3 border-t border-panel-border/70 pt-4"
                data-testid="project-setup-append-chapter-form"
                onSubmit={handleAppendChapterSubmit}
              >
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-append-chapter-file">Append chapter file (.txt)</Label>
                  <Input
                    accept=".txt,text/plain"
                    data-testid="project-setup-append-chapter-file-input"
                    id="project-setup-append-chapter-file"
                    onChange={(event) => {
                      const nextFile = event.target.files?.[0] ?? null;
                      setAppendChapterFile(nextFile);
                    }}
                    type="file"
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    Append chapter executes `POST /api/projects/:project_id/ingest/append-chapter` on existing corpus.
                  </p>
                  <Button data-testid="project-setup-append-chapter-submit" disabled={appendChapterBusy} type="submit">
                    {appendChapterBusy ? 'Appending chapter...' : 'Append Chapter'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Mode selection completion</CardTitle>
              <CardDescription>
                Select and apply mode using `GET /api/modes` and `PUT /api/projects/:project_id/mode`.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="grid gap-3" data-testid="project-setup-mode-form" onSubmit={handleModeSelectionSubmit}>
                <div className="grid gap-2">
                  <Label htmlFor="project-setup-mode-select">Mode</Label>
                  <NativeSelect
                    data-testid="project-setup-mode-select"
                    disabled={modeCatalogQuery.isLoading || switchModeMutation.isMutating}
                    id="project-setup-mode-select"
                    onChange={(event) => {
                      setSetupMode(event.target.value);
                    }}
                    value={effectiveSetupMode}
                  >
                    {modeOptions.map((modeOption) => (
                      <option key={modeOption} value={modeOption}>
                        {modeOption}
                      </option>
                    ))}
                  </NativeSelect>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    Switching mode marks downstream run artifacts stale and may require reruns.
                  </p>
                  <Button data-testid="project-setup-mode-submit" disabled={switchModeMutation.isMutating} type="submit">
                    {switchModeMutation.isMutating ? 'Applying mode...' : 'Apply mode'}
                  </Button>
                </div>
              </form>
              <AlertDialog open={isModeSwitchConfirmOpen} onOpenChange={handleModeSwitchConfirmOpenChange}>
                <AlertDialogContent data-testid="project-setup-mode-switch-confirm-dialog">
                  <AlertDialogHeader>
                    <AlertDialogTitle>Confirm mode switch?</AlertDialogTitle>
                    <AlertDialogDescription>
                      <strong className="text-foreground">{currentSetupMode}</strong>
                      {' -> '}
                      <strong className="text-foreground">{pendingSetupModeSwitch ?? effectiveSetupMode}</strong>. Existing run
                      outputs may be marked stale and require reruns before export delivery.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel data-testid="project-setup-mode-switch-confirm-cancel">Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      data-testid="project-setup-mode-switch-confirm-submit"
                      disabled={switchModeMutation.isMutating}
                      onClick={() => void handleModeSwitchConfirmSubmit()}
                    >
                      {switchModeMutation.isMutating ? 'Applying mode...' : 'Switch mode'}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </CardContent>
          </Card>

          <Card data-testid="project-setup-character-voice-readiness">
            <CardHeader>
              <CardTitle>Character + voice readiness</CardTitle>
              <CardDescription>Baseline checks for optional setup readiness before first production run.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-panel-border/70 px-3 py-3"
                data-testid="project-setup-character-readiness"
              >
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Character mapping</p>
                  <p className="text-xs text-muted-foreground">
                    Review/extract/import characters and finalize map before long runs.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={characterMappingStep?.ready ? 'default' : 'secondary'}>
                    {characterMappingStep ? toStepStatusLabel(characterMappingStep.ready, characterMappingStep.required) : 'Optional'}
                  </Badge>
                  <Button
                    data-testid="project-setup-go-characters"
                    onClick={() => navigate(`/projects/${projectId}/characters`)}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    Open Characters
                  </Button>
                </div>
              </div>

              <div
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-panel-border/70 px-3 py-3"
                data-testid="project-setup-voice-readiness"
              >
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Voice mapping</p>
                  <p className="text-xs text-muted-foreground">
                    Configure narrator/default voices and review character voice assignments.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={voiceMappingStep?.ready ? 'default' : 'secondary'}>
                    {voiceMappingStep ? toStepStatusLabel(voiceMappingStep.ready, voiceMappingStep.required) : 'Optional'}
                  </Badge>
                  <Button
                    data-testid="project-setup-go-pipeline-setup"
                    onClick={() => navigate(`/projects/${projectId}/pipeline-setup`)}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    Open Pipeline Setup
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Checklist</CardTitle>
              <CardDescription>Backend-driven setup status (`GET /api/projects/:project_id/setup-status`).</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {setupSteps.map((step) => (
                <div
                  className="flex items-center justify-between rounded-lg border border-panel-border/70 px-3 py-2"
                  data-testid={`project-setup-step-${step.step_id}`}
                  key={step.step_id}
                >
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-foreground">{step.label}</p>
                    <p className="text-xs text-muted-foreground">{step.step_id}</p>
                  </div>
                  <Badge variant={step.ready ? 'default' : 'secondary'}>{toStepStatusLabel(step.ready, step.required)}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </WorkflowPageShell>
  );
}
