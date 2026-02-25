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
            <CardDescription>Create a project to obtain a project ID.</CardDescription>
          </CardHeader>
          <CardContent className="flex h-full flex-col">
            <form className="flex h-full flex-col gap-4" onSubmit={handleCreateProject}>
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

              <div className="mt-auto space-y-2">
                <Button data-testid="create-project-button" disabled={isBusy} type="submit">
                  {createProjectMutation.isMutating ? 'Creating...' : 'Create Project'}
                </Button>
                {projectId !== null ? (
                  <p className="text-sm text-muted-foreground" data-testid="project-created-state">
                    Current project ID: <strong>{projectId}</strong>
                  </p>
                ) : null}
                <p className="text-sm text-muted-foreground">{projectId !== null ? 'Project created.' : 'Create a project to continue.'}</p>
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

              <div className="mt-auto space-y-2">
                <Button data-testid="upload-txt-button" disabled={isBusy || projectId === null} type="submit">
                  {ingestTxtMutation.isMutating ? 'Uploading...' : 'Upload & Parse'}
                </Button>
                <p className="text-sm text-muted-foreground" data-testid="chapter-count-state">
                  {chapterCount !== null ? `Detected chapters: ${chapterCount}` : 'Detected chapters: not available yet'}
                </p>
                {canContinue ? <p className="text-sm text-primary">Ready to continue.</p> : null}
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
