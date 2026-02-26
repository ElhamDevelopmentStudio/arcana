import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useRunDetailQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';
import { ChevronRight, LineChart, ShieldAlert, TriangleAlert, Waves } from 'lucide-react';

export function ProjectRunMonitorPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const runDetailQuery = useRunDetailQuery(projectId, runId);
  const llmExecutionMode = runDetailQuery.data?.config?.llm_execution_mode;
  const isRuleOnlyMode =
    typeof llmExecutionMode === 'object' &&
    llmExecutionMode !== null &&
    'mode' in llmExecutionMode &&
    (llmExecutionMode as Record<string, unknown>).mode === 'rule_only';
  const llmExecutionModeReason =
    typeof llmExecutionMode === 'object' &&
    llmExecutionMode !== null &&
    'reason' in llmExecutionMode &&
    typeof (llmExecutionMode as Record<string, unknown>).reason === 'string'
      ? (llmExecutionMode as Record<string, unknown>).reason
      : null;
  const llmExecutionModeProvider =
    typeof llmExecutionMode === 'object' &&
    llmExecutionMode !== null &&
    'provider' in llmExecutionMode &&
    typeof (llmExecutionMode as Record<string, unknown>).provider === 'string'
      ? (llmExecutionMode as Record<string, unknown>).provider
      : null;

  const runStatus = runDetailQuery.data?.status ?? 'not-started';
  const segmentCount = runDetailQuery.data?.segment_count ?? 0;

  return (
    <WorkflowPageShell
      step="Step 05"
      title="Run Monitor"
      description="Observe run execution state, logs, and progress events for a single project run."
      showOutputDisclaimer
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
            <Button
              disabled={runId === null}
              onClick={() => navigate(projectRoute(projectId, 'review/low-confidence'))}
              variant="outline"
            >
              <ShieldAlert className="size-4" />
              Review low-confidence regions
            </Button>
            <Button
              disabled={runId === null}
              onClick={() => navigate(projectRoute(projectId, 'guide/low-confidence-review'))}
              variant="outline"
            >
              How to review low-confidence outputs
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
            {isRuleOnlyMode ? (
              <Alert data-testid="llm-degraded-banner" className="border-amber-400/50 bg-amber-50">
                <TriangleAlert className="text-amber-600" />
                <AlertTitle>LLM availability is degraded</AlertTitle>
                <AlertDescription>
                  The pipeline is running in rule-only mode because one or more LLM providers were unavailable.
                  {llmExecutionModeReason ? <p>Reason: {llmExecutionModeReason}</p> : null}
                  {llmExecutionModeProvider ? <p>Last attempted provider: {llmExecutionModeProvider}</p> : null}
                </AlertDescription>
              </Alert>
            ) : null}

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
