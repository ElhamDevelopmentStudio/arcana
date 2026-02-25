import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useRunDetailQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';
import { ChevronRight, LineChart, Waves } from 'lucide-react';

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
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={runId === null}
              onClick={() => navigate(projectRoute(projectId, 'review/speakers'))}
              variant="outline"
            >
              Review speaker tags
            </Button>
            <Button
              disabled={runId === null}
              onClick={() => navigate(projectRoute(projectId, 'review/emotions'))}
              variant="outline"
            >
              <LineChart className="size-4" />
              Review emotional peaks
            </Button>
            <Button disabled={runId === null} onClick={() => navigate(projectRoute(projectId, 'export'))}>
              Continue to Export <ChevronRight className="size-4" />
            </Button>
          </div>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Run Lifecycle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <div className="grid gap-1">
              <p>
                Status: <strong className="text-foreground">{runStatus}</strong>
              </p>
              <p>
                Project: <strong className="text-foreground">{projectId ?? 'n/a'}</strong>
              </p>
              <p>
                Run: <strong className="text-foreground">{runId ?? 'n/a'}</strong>
              </p>
              <p>
                Segments: <strong className="text-foreground">{segmentCount}</strong>
              </p>
            </div>

            {runDetailQuery.isLoading ? <p>Loading run detail...</p> : null}
            {runDetailQuery.error ? <p className="text-destructive">{runDetailQuery.error.message}</p> : null}

            {runDetailQuery.data ? (
              <pre className="max-h-72 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
                {JSON.stringify(runDetailQuery.data, null, 2)}
              </pre>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Waves className="size-4 text-primary" />
              Event Stream
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            {(runDetailQuery.data?.llm_calls ?? []).slice(0, 6).map((call) => (
              <div key={call.id} className="rounded-xl bg-background/70 px-3 py-2">
                <p className="font-medium text-foreground">{call.provider}</p>
                <p className="text-xs">task: {call.task_type}</p>
                <p className="text-xs">requests: {call.request_count}</p>
              </div>
            ))}
            {!runDetailQuery.data?.llm_calls?.length ? <p>No call-level events yet.</p> : null}
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
