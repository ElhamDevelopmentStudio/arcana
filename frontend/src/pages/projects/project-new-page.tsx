import { type FormEvent, useState } from 'react';

import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { BookOpenText, FileText } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { Checkbox } from '@/components/ui/checkbox';
import {
  useAppendChapterMutation,
  useCreateProjectDraftMutation,
  useCreateProjectMutation,
  useIngestChapterDirectoryMutation,
  useIngestEpubMutation,
  useIngestMarkdownMutation,
  useIngestTxtMutation,
} from '@/features/workflow/api/workflow-hooks';
import { projectRoute } from '@/features/workflow/utils/project-route';

type IngestionSource = 'txt' | 'directory' | 'markdown' | 'epub';
type ProjectCreationMode = 'project' | 'draft';

export function ProjectNewPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('Shadow Slave PoC');
  const [projectCreationMode, setProjectCreationMode] = useState<ProjectCreationMode>('project');
  const [ingestionSource, setIngestionSource] = useState<IngestionSource>('txt');
  const [txtFile, setTxtFile] = useState<File | null>(null);
  const [directoryFiles, setDirectoryFiles] = useState<File[]>([]);
  const [markdownFile, setMarkdownFile] = useState<File | null>(null);
  const [epubFile, setEpubFile] = useState<File | null>(null);
  const [appendChapterFile, setAppendChapterFile] = useState<File | null>(null);
  const [doNotStoreSourceText, setDoNotStoreSourceText] = useState(false);

  const projectId = useWorkspaceStore((state) => state.projectId);
  const chapterCount = useWorkspaceStore((state) => state.chapterCount);
  const setProject = useWorkspaceStore((state) => state.setProject);
  const setChapterCount = useWorkspaceStore((state) => state.setChapterCount);

  const createProjectMutation = useCreateProjectMutation();
  const createProjectDraftMutation = useCreateProjectDraftMutation();
  const ingestTxtMutation = useIngestTxtMutation(projectId);
  const ingestDirectoryMutation = useIngestChapterDirectoryMutation(projectId);
  const ingestMarkdownMutation = useIngestMarkdownMutation(projectId);
  const ingestEpubMutation = useIngestEpubMutation(projectId);
  const appendChapterMutation = useAppendChapterMutation(projectId);

  const isBusy =
    createProjectMutation.isMutating ||
    createProjectDraftMutation.isMutating ||
    ingestTxtMutation.isMutating ||
    ingestDirectoryMutation.isMutating ||
    ingestMarkdownMutation.isMutating ||
    ingestEpubMutation.isMutating ||
    appendChapterMutation.isMutating;
  const canContinue = projectId !== null && chapterCount !== null;

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) {
      toast.error('Project title is required.');
      return;
    }

    try {
      const createProjectPayload = {
        title: title.trim(),
        do_not_store_source_text: doNotStoreSourceText,
      };
      const project =
        projectCreationMode === 'draft'
          ? await createProjectDraftMutation.trigger(createProjectPayload)
          : await createProjectMutation.trigger(createProjectPayload);
      setProject({
        projectId: project.id,
        projectTitle: project.title,
        selectedMode: null,
      });
      toast.success(projectCreationMode === 'draft' ? `Draft project created: #${project.id}` : `Project created: #${project.id}`);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : projectCreationMode === 'draft'
            ? 'Failed to create draft project'
            : 'Failed to create project',
      );
    }
  }

  async function handleIngestTxt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Create a project first.');
      return;
    }

    if (ingestionSource === 'txt') {
      if (!txtFile) {
        toast.error('Choose a TXT file before upload.');
        return;
      }

      try {
        const response = await ingestTxtMutation.trigger({ file: txtFile });
        setChapterCount(response.chapter_count);
        toast.success(`Ingestion complete: ${response.chapter_count} chapters detected.`);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'TXT ingestion failed.');
      }
      return;
    }

    if (ingestionSource === 'directory') {
      if (directoryFiles.length === 0) {
        toast.error('Choose chapter TXT files before upload.');
        return;
      }

      try {
        const response = await ingestDirectoryMutation.trigger({ files: directoryFiles });
        setChapterCount(response.chapter_count);
        toast.success(`Directory ingestion complete: ${response.chapter_count} chapters detected.`);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Chapter directory ingestion failed.');
      }
      return;
    }

    if (ingestionSource === 'markdown') {
      if (!markdownFile) {
        toast.error('Choose a Markdown file before upload.');
        return;
      }

      try {
        const response = await ingestMarkdownMutation.trigger({ file: markdownFile });
        setChapterCount(response.chapter_count);
        toast.success(`Markdown ingestion complete: ${response.chapter_count} chapters detected.`);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Markdown ingestion failed.');
      }
      return;
    }

    if (ingestionSource === 'epub') {
      if (!epubFile) {
        toast.error('Choose an EPUB file before upload.');
        return;
      }

      try {
        const response = await ingestEpubMutation.trigger({ file: epubFile });
        setChapterCount(response.chapter_count);
        toast.success(`EPUB ingestion complete: ${response.chapter_count} chapters detected.`);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'EPUB ingestion failed.');
      }
      return;
    }

    toast.info('This ingestion source is not available yet.');
  }

  async function handleAppendChapter() {
    if (projectId === null) {
      toast.error('Create a project first.');
      return;
    }
    if (!appendChapterFile) {
      toast.error('Choose a chapter TXT file before append.');
      return;
    }

    try {
      const response = await appendChapterMutation.trigger({ file: appendChapterFile });
      setChapterCount(response.chapter_count);
      setAppendChapterFile(null);
      toast.success(`Chapter appended. Total chapters: ${response.chapter_count}.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Append chapter failed.');
    }
  }

  return (
    <WorkflowPageShell
      step="Step 01"
      title="Create Project"
      description="Complete two actions in order: create a project, then ingest text."
      action={
        canContinue && projectId !== null ? (
          <Button onClick={() => navigate(projectRoute(projectId, 'mode'))}>Continue to Mode Selection</Button>
        ) : (
          <p className="text-sm text-muted-foreground">Complete both actions to continue.</p>
        )
      }
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="h-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="size-4 text-primary" />
              Project Setup
            </CardTitle>
            <CardDescription>Create either a standard project or a draft to obtain a project ID.</CardDescription>
          </CardHeader>
          <CardContent className="flex h-full flex-col">
            <form className="flex h-full flex-col gap-4" onSubmit={handleCreateProject}>
              <div className="grid gap-2">
                <Label htmlFor="project-creation-mode">Creation type</Label>
                <NativeSelect
                  id="project-creation-mode"
                  data-testid="project-creation-mode-select"
                  value={projectCreationMode}
                  onChange={(event) => setProjectCreationMode(event.target.value as ProjectCreationMode)}
                >
                  <option value="project">Project (POST /api/projects)</option>
                  <option value="draft">Draft (POST /api/projects/drafts)</option>
                </NativeSelect>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="project-title">Project title</Label>
                <Input
                  id="project-title"
                  data-testid="project-title-input"
                  placeholder="e.g., Shadow Slave PoC"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>
              <div className="flex items-start gap-2">
                <Checkbox
                  id="do-not-store-source-text"
                  checked={doNotStoreSourceText}
                  onCheckedChange={(checked) => setDoNotStoreSourceText(checked === true)}
                />
                <Label htmlFor="do-not-store-source-text" className="text-sm leading-relaxed">
                  Store only derived metrics
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">
                Enable this to avoid retaining raw source text while keeping normalized content and derived artifacts.
              </p>

              <div className="mt-auto space-y-2">
                <Button data-testid="create-project-button" disabled={isBusy} type="submit">
                  {createProjectMutation.isMutating || createProjectDraftMutation.isMutating
                    ? 'Creating...'
                    : projectCreationMode === 'draft'
                      ? 'Create Draft'
                      : 'Create Project'}
                </Button>
                {projectId !== null ? (
                  <p className="text-sm text-muted-foreground" data-testid="project-created-state">
                    Current project ID: <strong>{projectId}</strong>
                  </p>
                ) : null}
                <p className="text-sm text-muted-foreground">
                  {projectId !== null
                    ? projectCreationMode === 'draft'
                      ? 'Draft project created.'
                      : 'Project created.'
                    : 'Create a project to continue.'}
                </p>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card className="h-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpenText className="size-4 text-primary" />
              Ingestion
            </CardTitle>
            <CardDescription>Upload source text and verify detected chapter count.</CardDescription>
          </CardHeader>
          <CardContent className="flex h-full flex-col">
            <form className="flex h-full flex-col gap-4" onSubmit={handleIngestTxt}>
              <div className="grid gap-2">
                <Label htmlFor="ingestion-source">Source type</Label>
                <NativeSelect
                  id="ingestion-source"
                  data-testid="ingestion-source-select"
                  value={ingestionSource}
                  onChange={(event) => setIngestionSource(event.target.value as IngestionSource)}
                >
                  <option value="txt">TXT file</option>
                  <option value="directory">Chapter directory</option>
                  <option value="markdown">Markdown</option>
                  <option value="epub">EPUB</option>
                </NativeSelect>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="txt-upload">
                  {ingestionSource === 'directory'
                    ? 'Upload chapter TXT files'
                    : ingestionSource === 'markdown'
                      ? 'Upload Markdown file'
                      : ingestionSource === 'epub'
                        ? 'Upload EPUB file'
                        : 'Upload TXT'}
                </Label>
                {ingestionSource === 'directory' ? (
                  <Input
                    id="txt-upload"
                    accept=".txt"
                    data-testid="directory-upload-input"
                    multiple
                    onChange={(event) => setDirectoryFiles(Array.from(event.target.files ?? []))}
                    type="file"
                  />
                ) : ingestionSource === 'markdown' ? (
                  <Input
                    id="txt-upload"
                    accept=".md,.markdown"
                    data-testid="markdown-upload-input"
                    onChange={(event) => setMarkdownFile(event.target.files?.[0] ?? null)}
                    type="file"
                  />
                ) : ingestionSource === 'epub' ? (
                  <Input
                    id="txt-upload"
                    accept=".epub"
                    data-testid="epub-upload-input"
                    onChange={(event) => setEpubFile(event.target.files?.[0] ?? null)}
                    type="file"
                  />
                ) : (
                  <Input
                    id="txt-upload"
                    accept=".txt"
                    data-testid="txt-upload-input"
                    disabled={ingestionSource !== 'txt'}
                    onChange={(event) => setTxtFile(event.target.files?.[0] ?? null)}
                    type="file"
                  />
                )}
              </div>

              <div className="mt-auto space-y-2">
                <Button data-testid="upload-txt-button" disabled={isBusy || projectId === null} type="submit">
                  {ingestTxtMutation.isMutating ||
                  ingestDirectoryMutation.isMutating ||
                  ingestMarkdownMutation.isMutating ||
                  ingestEpubMutation.isMutating
                    ? 'Uploading...'
                    : 'Upload & Parse'}
                </Button>
                <p className="text-sm text-muted-foreground" data-testid="chapter-count-state">
                  {chapterCount !== null ? `Detected chapters: ${chapterCount}` : 'Detected chapters: not available yet'}
                </p>
                <div className="mt-3 rounded-xl border border-border/70 bg-muted/20 p-3">
                  <p className="text-sm font-medium text-foreground">Append one chapter</p>
                  <p className="text-xs text-muted-foreground">Use this after initial ingestion for incremental chapter additions.</p>
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
                    <Input
                      accept=".txt"
                      data-testid="append-chapter-upload-input"
                      onChange={(event) => setAppendChapterFile(event.target.files?.[0] ?? null)}
                      type="file"
                    />
                    <Button
                      data-testid="append-chapter-button"
                      disabled={isBusy || projectId === null}
                      onClick={handleAppendChapter}
                      type="button"
                    >
                      {appendChapterMutation.isMutating ? 'Appending...' : 'Append Chapter'}
                    </Button>
                  </div>
                </div>
                {canContinue ? <p className="text-sm text-primary">Ready to continue.</p> : null}
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
