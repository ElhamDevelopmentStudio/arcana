import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';
import { Download } from 'lucide-react';

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
      showOutputDisclaimer
      action={
        projectId !== null ? (
          <Button onClick={() => navigate(projectRoute(projectId, 'dashboards'))}>Continue to Dashboards</Button>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Export Package</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>Project: {projectId ?? 'n/a'}</p>
          <p>Run: {runId ?? 'n/a'}</p>
          <p>{exportPayloadQuery.data ? 'Export payload is ready for download.' : 'Awaiting run/export data.'}</p>

          <Button disabled={!exportPayloadQuery.data} onClick={downloadExportJson}>
            <Download className="size-4" />
            Download JSON
          </Button>

          {exportPayloadQuery.isLoading ? <p>Loading export payload...</p> : null}
          {exportPayloadQuery.error ? <p className="text-destructive">{exportPayloadQuery.error.message}</p> : null}
          {exportPayloadQuery.data ? (
            <pre className="max-h-72 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
              {JSON.stringify(exportPayloadQuery.data, null, 2)}
            </pre>
          ) : (
            <p>JSON/CSV/chunked export links and manifest metadata with deterministic run context.</p>
          )}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
