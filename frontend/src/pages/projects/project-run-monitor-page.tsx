import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useRunDetailQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';

export function ProjectRunMonitorPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const runDetailQuery = useRunDetailQuery(projectId, runId);

  const runStatus = runDetailQuery.data?.status ?? 'not-started';
  const segmentCount = runDetailQuery.data?.segment_count ?? 0;

  return (
    <WorkflowPageShell
      step="Step 05"
      title="Run Monitor"
      description="Observe run execution state, logs, and progress events for a single project run."
      action={
        projectId !== null ? (
          <Button disabled={runId === null} onClick={() => navigate(projectRoute(projectId, 'export'))}>
            Continue to Export
          </Button>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Run Lifecycle</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">Project: {projectId ?? 'n/a'}</Badge>
            <Badge variant="outline">Run: {runId ?? 'n/a'}</Badge>
            <Badge variant={runStatus === 'completed' ? 'default' : 'secondary'}>Status: {runStatus}</Badge>
            <Badge variant="outline">Segments: {segmentCount}</Badge>
          </div>

          {runDetailQuery.isLoading ? <p>Loading run detail...</p> : null}
          {runDetailQuery.error ? <p className="text-destructive">{runDetailQuery.error.message}</p> : null}

          {runDetailQuery.data ? (
            <pre className="max-h-72 overflow-auto rounded-lg border bg-muted/30 p-3 text-xs">
              {JSON.stringify(runDetailQuery.data, null, 2)}
            </pre>
          ) : null}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
