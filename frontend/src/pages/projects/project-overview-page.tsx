import { useNavigate, useParams } from 'react-router-dom';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { ApiPanelError, ApiPanelLoading } from '@/components/ui/api-panel-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useProjectDetailQuery, useProjectWorkspaceSummaryQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectOverviewPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;
  const projectDetailQuery = useProjectDetailQuery(projectId);
  const workspaceSummaryQuery = useProjectWorkspaceSummaryQuery(projectId);

  const projectDetailErrorMessage =
    projectDetailQuery.error instanceof Error ? projectDetailQuery.error.message : 'Unable to load project detail.';
  const workspaceSummaryErrorMessage =
    workspaceSummaryQuery.error instanceof Error
      ? workspaceSummaryQuery.error.message
      : 'Unable to load project workspace summary.';

  return (
    <WorkflowPageShell
      description="Project-level overview composed from detail and workspace summary contracts."
      step="Overview"
      title="Project Overview"
      action={
        projectId !== null ? (
          <Button data-testid="project-overview-open-setup" onClick={() => navigate(`/projects/${projectId}/setup`)}>
            Open Setup
          </Button>
        ) : undefined
      }
    >
      {projectId === null ? (
        <Card data-testid="project-overview-project-required">
          <CardHeader>
            <CardTitle>Project required</CardTitle>
            <CardDescription>Select or create a project before opening overview.</CardDescription>
          </CardHeader>
        </Card>
      ) : projectDetailQuery.isLoading && projectDetailQuery.data === undefined ? (
        <div data-testid="project-overview-loading">
          <ApiPanelLoading description="Fetching project detail and workspace summary contracts." title="Loading project overview" />
        </div>
      ) : projectDetailQuery.error ? (
        <div data-testid="project-overview-project-detail-error">
          <ApiPanelError
            description={projectDetailErrorMessage}
            onRetry={() => {
              void projectDetailQuery.mutate();
            }}
            retryLabel="Retry project detail"
            title="Project detail unavailable"
          />
        </div>
      ) : workspaceSummaryQuery.error ? (
        <div data-testid="project-overview-workspace-summary-error">
          <ApiPanelError
            description={workspaceSummaryErrorMessage}
            onRetry={() => {
              void workspaceSummaryQuery.mutate();
            }}
            retryLabel="Retry workspace summary"
            title="Workspace summary unavailable"
          />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2" data-testid="project-overview-ready">
          <Card data-testid="project-overview-detail-card">
            <CardHeader>
              <CardDescription>From `GET /api/projects/{'{project_id}'}`</CardDescription>
              <CardTitle>{projectDetailQuery.data?.title ?? `Project #${projectId}`}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>Project ID: {projectDetailQuery.data?.project_id ?? projectId}</p>
              <p>Lifecycle: {projectDetailQuery.data?.lifecycle_state ?? 'draft'}</p>
              <p>Next action: {projectDetailQuery.data?.next_required_action ?? 'none'}</p>
              <p>Mode: {projectDetailQuery.data?.selected_mode ?? 'n/a'}</p>
              <p>LLM enabled: {projectDetailQuery.data?.llm_enabled ? 'yes' : 'no'}</p>
              <p>Character map finalized: {projectDetailQuery.data?.character_map_finalized ? 'yes' : 'no'}</p>
              {projectDetailQuery.data?.description ? (
                <p className="text-foreground/90">{projectDetailQuery.data.description}</p>
              ) : (
                <p>No description provided.</p>
              )}
              {projectDetailQuery.data?.tags?.length ? (
                <div className="flex flex-wrap gap-2">
                  {projectDetailQuery.data.tags.map((tag) => (
                    <Badge key={tag} variant="outline">
                      {tag}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card data-testid="project-overview-workspace-summary-card">
            <CardHeader>
              <CardDescription>From `GET /api/projects/{'{project_id}'}/workspace-summary`</CardDescription>
              <CardTitle>Workspace health</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>Setup complete: {workspaceSummaryQuery.data?.is_setup_complete ? 'yes' : 'no'}</p>
              <p>Chapters: {workspaceSummaryQuery.data?.chapters_count ?? 0}</p>
              <p>Characters: {workspaceSummaryQuery.data?.characters_count ?? 0}</p>
              <p>Voice mappings: {workspaceSummaryQuery.data?.voice_mappings_count ?? 0}</p>
              <p>Runs total: {workspaceSummaryQuery.data?.runs_total_count ?? 0}</p>
              <p>Runs completed: {workspaceSummaryQuery.data?.runs_completed_count ?? 0}</p>
              <p>Runs failed: {workspaceSummaryQuery.data?.runs_failed_count ?? 0}</p>
              <p>Last run status: {workspaceSummaryQuery.data?.last_run_status ?? 'none'}</p>
              <p>Last export: {workspaceSummaryQuery.data?.last_export_at ?? 'none'}</p>
            </CardContent>
          </Card>
        </div>
      )}
    </WorkflowPageShell>
  );
}
