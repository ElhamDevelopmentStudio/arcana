import { type FormEvent, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { ApiPanelError, ApiPanelLoading } from '@/components/ui/api-panel-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  useAttachInitialIngestionSourceMutation,
  useIngestTxtMutation,
  useProjectSetupStatusQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

const setupStatusPollIntervalMs = 3000;

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

export function ProjectSetupPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const setChapterCount = useWorkspaceStore((state) => state.setChapterCount);
  const projectId = routeProjectId ?? storeProjectId;
  const [ingestionFile, setIngestionFile] = useState<File | null>(null);

  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const attachInitialIngestionSourceMutation = useAttachInitialIngestionSourceMutation(projectId);
  const ingestTxtMutation = useIngestTxtMutation(projectId);

  const setupErrorMessage =
    setupStatusQuery.error instanceof Error
      ? setupStatusQuery.error.message
      : 'Unable to load setup checklist.';
  const setupSteps = setupStatusQuery.data?.steps ?? [];
  const ingestionBusy = attachInitialIngestionSourceMutation.isMutating || ingestTxtMutation.isMutating;

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
      try {
        await attachInitialIngestionSourceMutation.trigger({
          source: 'txt',
          source_filename: ingestionFile.name,
        });
      } catch (error) {
        if (!isAlreadyAttachedIngestionSourceError(error)) {
          throw error;
        }
      }

      const response = await ingestTxtMutation.trigger({ file: ingestionFile });
      setChapterCount(response.chapter_count);
      toast.success(`Ingestion complete: ${response.chapter_count} chapters detected.`);
      setIngestionFile(null);
      await setupStatusQuery.mutate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Setup ingestion failed.');
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
              <CardTitle>Source attach + ingestion</CardTitle>
              <CardDescription>
                Attach initial source metadata (`POST /api/projects/:project_id/ingest/source`) and ingest TXT now.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="grid gap-3" data-testid="project-setup-ingestion-form" onSubmit={handleIngestionSubmit}>
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
                    Setup step currently supports TXT ingestion in this route.
                  </p>
                  <Button data-testid="project-setup-ingestion-submit" disabled={ingestionBusy} type="submit">
                    {ingestionBusy ? 'Ingesting...' : 'Attach source and ingest'}
                  </Button>
                </div>
              </form>
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
