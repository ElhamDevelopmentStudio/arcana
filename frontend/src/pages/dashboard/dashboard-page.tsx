import { useNavigate } from 'react-router-dom';

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

export function DashboardPage() {
  const navigate = useNavigate();
  const setProject = useWorkspaceStore((state) => state.setProject);
  const summaryQuery = useProjectControlPanelSummaryQuery(true);
  const listQuery = useProjectControlPanelProjectListQuery(true, { page: 1, page_size: 20 });

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
                      navigate(toWorkflowRoute(item.project_id, item.next_required_action));
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

