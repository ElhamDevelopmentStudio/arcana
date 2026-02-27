import { Link, useParams } from 'react-router-dom';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ApiPanelError, ApiPanelLoading } from '@/components/ui/api-panel-state';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useProjectDetailQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectWorkspaceHomePage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;
  const projectDetailQuery = useProjectDetailQuery(projectId);

  const projectDetailErrorMessage =
    projectDetailQuery.error instanceof Error ? projectDetailQuery.error.message : 'Unable to load project detail.';

  if (projectId === null) {
    return (
      <Card data-testid="project-workspace-home-project-required">
        <CardHeader>
          <CardTitle>Project required</CardTitle>
          <CardDescription>Select or create a project before opening workspace home.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (projectDetailQuery.isLoading && projectDetailQuery.data === undefined) {
    return (
      <div data-testid="project-workspace-home-loading">
        <ApiPanelLoading description="Fetching project detail contract." title="Loading project detail" />
      </div>
    );
  }

  if (projectDetailQuery.error) {
    return (
      <div data-testid="project-workspace-home-error">
        <ApiPanelError
          description={projectDetailErrorMessage}
          onRetry={() => {
            void projectDetailQuery.mutate();
          }}
          retryLabel="Retry project detail"
          title="Project detail unavailable"
        />
      </div>
    );
  }

  return (
    <Card data-testid="project-workspace-home-ready">
      <CardHeader>
        <CardDescription data-testid="project-workspace-home-source-contract">
          From `GET /api/projects/{'{project_id}'}`
        </CardDescription>
        <CardTitle data-testid="project-workspace-home-title">{projectDetailQuery.data?.title ?? `Project #${projectId}`}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p data-testid="project-workspace-home-id">Project ID: {projectDetailQuery.data?.project_id ?? projectId}</p>
        <p data-testid="project-workspace-home-lifecycle">Lifecycle: {projectDetailQuery.data?.lifecycle_state ?? 'draft'}</p>
        <p data-testid="project-workspace-home-next-action">
          Next action: {projectDetailQuery.data?.next_required_action ?? 'none'}
        </p>
        <p data-testid="project-workspace-home-mode">Mode: {projectDetailQuery.data?.selected_mode ?? 'n/a'}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
            data-testid="project-workspace-home-open-overview"
            to="overview"
          >
            Open Overview
          </Link>
          <Link
            className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
            data-testid="project-workspace-home-open-setup"
            to="setup"
          >
            Open Setup
          </Link>
          <Link
            className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
            data-testid="project-workspace-home-open-runs"
            to="runs"
          >
            Open Runs
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
