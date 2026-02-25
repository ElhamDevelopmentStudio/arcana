import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';

export function ProjectExportPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);

  function downloadExportJson() {
    if (!exportPayloadQuery.data || projectId === null || runId === null) {
      return;
    }
    const blob = new Blob([JSON.stringify(exportPayloadQuery.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `project-${projectId}-run-${runId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <WorkflowPageShell
      step="Step 06"
      title="Exports"
      description="Review export readiness and download generated outputs. This page is dedicated to export artifacts only."
      action={
        projectId !== null ? (
          <Button onClick={() => navigate(projectRoute(projectId, 'dashboards'))}>Continue to Dashboards</Button>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Readiness</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>Blocking reasons and required preconditions for audiobook/academic/author exports.</p>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Project: {projectId ?? 'n/a'}</Badge>
              <Badge variant="outline">Run: {runId ?? 'n/a'}</Badge>
              <Badge variant={exportPayloadQuery.data ? 'default' : 'secondary'}>
                {exportPayloadQuery.data ? 'Export ready' : 'Awaiting run/export data'}
              </Badge>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Download Center</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <Button disabled={!exportPayloadQuery.data} onClick={downloadExportJson} variant="outline">
              Download JSON
            </Button>
            {exportPayloadQuery.isLoading ? <p>Loading export payload...</p> : null}
            {exportPayloadQuery.error ? <p className="text-destructive">{exportPayloadQuery.error.message}</p> : null}
            {exportPayloadQuery.data ? (
              <pre className="max-h-72 overflow-auto rounded-lg border bg-muted/30 p-3 text-xs">
                {JSON.stringify(exportPayloadQuery.data, null, 2)}
              </pre>
            ) : (
              <p>JSON/CSV/chunked export links and manifest metadata with deterministic run context.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
