import { useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import {
  projectControlPanelProjectListRequestSchema,
  type ProjectControlPanelProjectListRequestDto,
} from '@/app/schemas/api';
import { useUiRouteStateStore, type DashboardListQueryState } from '@/app/state/ui-route-state-store';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  useProjectControlPanelProjectListQuery,
  useProjectControlPanelSummaryQuery,
} from '@/features/workflow/api/workflow-hooks';

function toWorkflowRoute(projectId: number, nextRequiredAction: string) {
  if (nextRequiredAction === 'select_mode') {
    return `/projects/${projectId}/mode`;
  }
  if (nextRequiredAction === 'run' || nextRequiredAction === 'configure') {
    return `/projects/${projectId}/pipeline-setup`;
  }
  if (nextRequiredAction === 'export') {
    return `/projects/${projectId}/export`;
  }
  if (nextRequiredAction === 'rerun') {
    return `/projects/${projectId}/run-monitor`;
  }
  return '/projects/new';
}

function readDashboardQueryFromSearchParams(
  searchParams: URLSearchParams,
): ProjectControlPanelProjectListRequestDto {
  const raw = {
    page: searchParams.get('page') ? Number(searchParams.get('page')) : undefined,
    page_size: searchParams.get('page_size') ? Number(searchParams.get('page_size')) : undefined,
    status: searchParams.get('status') ?? undefined,
    selected_mode: searchParams.get('selected_mode') ?? undefined,
    last_run_status: searchParams.get('last_run_status') ?? undefined,
    next_required_action: searchParams.get('next_required_action') ?? undefined,
  };
  const parsed = projectControlPanelProjectListRequestSchema.safeParse(raw);
  if (!parsed.success) {
    return {};
  }
  return parsed.data;
}

function normalizeDashboardListQuery(
  fromUrl: ProjectControlPanelProjectListRequestDto,
  fallback: DashboardListQueryState,
): DashboardListQueryState {
  return {
    page: fromUrl.page ?? fallback.page,
    page_size: fromUrl.page_size ?? fallback.page_size,
    status: fromUrl.status ?? fallback.status,
    selected_mode: fromUrl.selected_mode ?? fallback.selected_mode,
    last_run_status: fromUrl.last_run_status ?? fallback.last_run_status,
    next_required_action: fromUrl.next_required_action ?? fallback.next_required_action,
  };
}

function buildDashboardSearchParams(query: DashboardListQueryState): URLSearchParams {
  const params = new URLSearchParams();
  params.set('page', String(query.page));
  params.set('page_size', String(query.page_size));
  if (query.status) {
    params.set('status', query.status);
  }
  if (query.selected_mode) {
    params.set('selected_mode', query.selected_mode);
  }
  if (query.last_run_status) {
    params.set('last_run_status', query.last_run_status);
  }
  if (query.next_required_action) {
    params.set('next_required_action', query.next_required_action);
  }
  return params;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const setProject = useWorkspaceStore((state) => state.setProject);
  const dashboardListQueryState = useUiRouteStateStore((state) => state.dashboardListQuery);
  const setDashboardListQuery = useUiRouteStateStore((state) => state.setDashboardListQuery);
  const getProjectLastRoute = useUiRouteStateStore((state) => state.getProjectLastRoute);

  const dashboardListQueryFromUrl = useMemo(
    () => readDashboardQueryFromSearchParams(searchParams),
    [searchParams],
  );
  const effectiveListQuery = useMemo(
    () => normalizeDashboardListQuery(dashboardListQueryFromUrl, dashboardListQueryState),
    [dashboardListQueryFromUrl, dashboardListQueryState],
  );

  useEffect(() => {
    setDashboardListQuery(effectiveListQuery);
  }, [effectiveListQuery, setDashboardListQuery]);

  useEffect(() => {
    const current = searchParams.toString();
    const nextParams = buildDashboardSearchParams(effectiveListQuery);
    const next = nextParams.toString();
    if (current !== next) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [effectiveListQuery, searchParams, setSearchParams]);

  const summaryQuery = useProjectControlPanelSummaryQuery(true);
  const listQuery = useProjectControlPanelProjectListQuery(true, effectiveListQuery);

  const listItems = listQuery.data?.items ?? [];

  return (
    <WorkflowPageShell
      action={
        <Button data-testid="dashboard-create-project" onClick={() => navigate('/projects/new')}>
          Create Project
        </Button>
      }
      description="Control panel for project lifecycle, run readiness, and next required actions."
      step="Dashboard"
      title="Project Control Panel"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Total projects</CardDescription>
            <CardTitle>{summaryQuery.data?.total_projects ?? 0}</CardTitle>
          </CardHeader>
          <CardContent />
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Active runs</CardDescription>
            <CardTitle>{summaryQuery.data?.active_run_count ?? 0}</CardTitle>
          </CardHeader>
          <CardContent />
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Recent failures</CardDescription>
            <CardTitle>{summaryQuery.data?.recent_failure_count ?? 0}</CardTitle>
          </CardHeader>
          <CardContent />
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Projects</CardTitle>
          <CardDescription>Live control-panel project list from backend contract.</CardDescription>
        </CardHeader>
        <CardContent>
          {listItems.length === 0 ? (
            <p className="text-sm text-muted-foreground">No projects found.</p>
          ) : (
            <div className="space-y-3" data-testid="dashboard-project-list">
              {listItems.map((item) => (
                <div
                  key={item.project_id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-panel-border/70 px-4 py-3"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      Project #{item.project_id}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="secondary">{item.status}</Badge>
                      <span>mode: {item.selected_mode}</span>
                      <span>next: {item.next_required_action}</span>
                      <span>updated: {new Date(item.updated_at).toLocaleString()}</span>
                    </div>
                  </div>
                  <Button
                    onClick={() => {
                      setProject({
                        projectId: item.project_id,
                        projectTitle: `Project ${item.project_id}`,
                        selectedMode: item.selected_mode,
                      });
                      const rememberedRoute = getProjectLastRoute(item.project_id);
                      navigate(rememberedRoute ?? toWorkflowRoute(item.project_id, item.next_required_action));
                    }}
                    size="sm"
                    variant="outline"
                  >
                    Open
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
