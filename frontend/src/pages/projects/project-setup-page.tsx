import { useParams } from 'react-router-dom';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { ApiPanelError, ApiPanelLoading } from '@/components/ui/api-panel-state';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useProjectSetupStatusQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

function toStepStatusLabel(ready: boolean, required: boolean) {
  if (ready) {
    return required ? 'Complete' : 'Optional complete';
  }
  return required ? 'Required' : 'Optional';
}

export function ProjectSetupPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;
  const setupStatusQuery = useProjectSetupStatusQuery(projectId);

  const setupErrorMessage =
    setupStatusQuery.error instanceof Error
      ? setupStatusQuery.error.message
      : 'Unable to load setup checklist.';
  const setupSteps = setupStatusQuery.data?.steps ?? [];

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
              </div>
            </CardHeader>
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
