import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';
import { Download, FileJson2, FileText, ShieldCheck, Table2 } from 'lucide-react';

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
      <div className="grid gap-4 lg:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4 text-primary" />
              Export Gate
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">{exportPayloadQuery.data ? 'ready' : 'waiting'}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileJson2 className="size-4 text-primary" />
              JSON
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">{exportPayloadQuery.data ? 'available' : 'pending'}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Table2 className="size-4 text-primary" />
              CSV
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">planned output</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="size-4 text-primary" />
              Manifest
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">deterministic metadata</CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
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
            <Button disabled={!exportPayloadQuery.data} onClick={downloadExportJson}>
              <Download className="size-4" />
              Download JSON
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Download Center</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            {exportPayloadQuery.isLoading ? <p>Loading export payload...</p> : null}
            {exportPayloadQuery.error ? <p className="text-destructive">{exportPayloadQuery.error.message}</p> : null}
            {exportPayloadQuery.data ? (
              <pre className="max-h-72 overflow-auto rounded-xl border bg-muted/35 p-3 text-xs">
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
