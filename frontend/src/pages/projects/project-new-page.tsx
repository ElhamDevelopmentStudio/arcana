import { type FormEvent, useState } from 'react';

import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { BookOpenText, CheckCircle2, FileText, FolderGit2, Sparkles } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { useCreateProjectMutation, useIngestTxtMutation } from '@/features/workflow/api/workflow-hooks';
import { projectRoute } from '@/features/workflow/utils/project-route';

type IngestionSource = 'txt' | 'directory' | 'markdown' | 'epub';

export function ProjectNewPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('Shadow Slave PoC');
  const [ingestionSource, setIngestionSource] = useState<IngestionSource>('txt');
  const [txtFile, setTxtFile] = useState<File | null>(null);

  const projectId = useWorkspaceStore((state) => state.projectId);
  const chapterCount = useWorkspaceStore((state) => state.chapterCount);
  const setProject = useWorkspaceStore((state) => state.setProject);
  const setChapterCount = useWorkspaceStore((state) => state.setChapterCount);

  const createProjectMutation = useCreateProjectMutation();
  const ingestTxtMutation = useIngestTxtMutation(projectId);

  const isBusy = createProjectMutation.isMutating || ingestTxtMutation.isMutating;
  const canContinue = projectId !== null && chapterCount !== null;

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) {
      toast.error('Project title is required.');
      return;
    }

    try {
      const project = await createProjectMutation.trigger({ title: title.trim() });
      setProject({
        projectId: project.id,
        projectTitle: project.title,
        selectedMode: null,
      });
      toast.success(`Project created: #${project.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create project');
    }
  }

  async function handleIngestTxt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Create a project first.');
      return;
    }

    if (ingestionSource !== 'txt') {
      toast.info('Only TXT ingestion is currently available in backend APIs.');
      return;
    }

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
  }

  return (
    <WorkflowPageShell
      step="Step 01"
      title="Create Project"
      description="Create a project and ingest source material. This page is intentionally scoped to project creation and ingestion only."
      action={
        canContinue && projectId !== null ? (
          <Button onClick={() => navigate(projectRoute(projectId, 'mode'))}>Continue to Mode Selection</Button>
        ) : (
          <Badge variant="outline">Complete setup to continue</Badge>
        )
      }
    >
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded-xl bg-primary/12 text-primary">
                <FolderGit2 className="size-4" />
              </span>
              Project Identity
            </CardTitle>
            <CardDescription>Initialize a workspace before configuring any downstream pipeline logic.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>Title and metadata are persisted as the root project context.</p>
            <p className="flex items-center gap-2 rounded-xl bg-secondary/50 px-3 py-2 text-secondary-foreground">
              <CheckCircle2 className="size-4 text-chart-3" />
              {projectId !== null ? `Project #${projectId} ready` : 'No project created yet'}
            </p>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded-xl bg-primary/12 text-primary">
                <BookOpenText className="size-4" />
              </span>
              Ingestion Scope
            </CardTitle>
            <CardDescription>Load chapterized source text for all subsequent mode and tagging passes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>TXT flow is active now. Other sources are scaffolded and ready for backend hookup.</p>
            <p className="rounded-xl bg-secondary/50 px-3 py-2 text-secondary-foreground">
              {chapterCount !== null ? `Detected chapters: ${chapterCount}` : 'Detected chapters: not available yet'}
            </p>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded-xl bg-primary/12 text-primary">
                <Sparkles className="size-4" />
              </span>
              Readiness Signal
            </CardTitle>
            <CardDescription>When project and ingestion are both complete, the mode step unlocks automatically.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p className="rounded-xl bg-primary/9 px-3 py-2 text-primary">
              {canContinue ? 'Ready to proceed to mode selection.' : 'Complete project creation and ingestion first.'}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="size-4 text-primary" />
              Project Setup
            </CardTitle>
            <CardDescription>Create one project before moving to downstream workflow pages.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-3" onSubmit={handleCreateProject}>
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
              <Button data-testid="create-project-button" disabled={isBusy} type="submit">
                {createProjectMutation.isMutating ? 'Creating...' : 'Create Project'}
              </Button>
              {projectId !== null ? (
                <p className="text-sm text-muted-foreground" data-testid="project-created-state">
                  Current project ID: <strong>{projectId}</strong>
                </p>
              ) : null}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpenText className="size-4 text-primary" />
              Ingestion
            </CardTitle>
            <CardDescription>Select source type, upload input, and verify chapter detection results.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-3" onSubmit={handleIngestTxt}>
              <div className="grid gap-2">
                <Label htmlFor="ingestion-source">Source type</Label>
                <NativeSelect
                  id="ingestion-source"
                  data-testid="ingestion-source-select"
                  value={ingestionSource}
                  onChange={(event) => setIngestionSource(event.target.value as IngestionSource)}
                >
                  <option value="txt">TXT file</option>
                  <option value="directory">Chapter directory (pending backend)</option>
                  <option value="markdown">Markdown (pending backend)</option>
                  <option value="epub">EPUB (pending backend)</option>
                </NativeSelect>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="txt-upload">Upload TXT</Label>
                <Input
                  id="txt-upload"
                  accept=".txt"
                  data-testid="txt-upload-input"
                  disabled={ingestionSource !== 'txt'}
                  onChange={(event) => setTxtFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </div>

              <Button data-testid="upload-txt-button" disabled={isBusy || projectId === null} type="submit">
                {ingestTxtMutation.isMutating ? 'Uploading...' : 'Upload & Parse'}
              </Button>

              <p className="text-sm text-muted-foreground" data-testid="chapter-count-state">
                {chapterCount !== null ? `Detected chapters: ${chapterCount}` : 'Detected chapters: not available yet'}
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
