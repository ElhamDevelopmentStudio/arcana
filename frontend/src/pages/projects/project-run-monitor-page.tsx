import { useEffect, useMemo, useState } from 'react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  useAudiobookPrepDashboardQuery,
  useCancelRunMutation,
  useCharacterAnalyticsQuery,
  useCharacterCooccurrenceGraphQuery,
  usePipelineStageDurationsDashboardQuery,
  usePolarityGraphQuery,
  useRecoverRunMutation,
  useRerunRunMutation,
  useRunConfigDiffQuery,
  useRunConfigPresetMutation,
  useRunDetailQuery,
  useTensionGraphQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';
import { ChevronRight, LineChart, ShieldAlert, TriangleAlert, Waves } from 'lucide-react';

const runMonitorRefreshIntervalMs = 4000;
const runMutationRecoveryStorageKey = 'nipe-run-monitor-pending-mutation';
const runMutationRecoveryMaxAgeMs = 10 * 60_000;

type PendingRunMutationRecoveryRecord = {
  projectId: number;
  sourceRunId: number;
  trackedRunId: number;
  mutation: 'rerun' | 'recover' | 'cancel';
  startedAt: string;
};

function isRunStatusActive(status: string | null | undefined) {
  return status === 'queued' || status === 'running';
}

function isRunStatusTerminal(status: string | null | undefined) {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

function parsePendingRunMutationRecovery(rawValue: string | null): PendingRunMutationRecoveryRecord | null {
  if (!rawValue) {
    return null;
  }
  try {
    const parsed = JSON.parse(rawValue) as Partial<PendingRunMutationRecoveryRecord>;
    if (
      !parsed
      || typeof parsed !== 'object'
      || !Number.isInteger(parsed.projectId)
      || !Number.isInteger(parsed.sourceRunId)
      || !Number.isInteger(parsed.trackedRunId)
      || !['rerun', 'recover', 'cancel'].includes(parsed.mutation ?? '')
      || typeof parsed.startedAt !== 'string'
    ) {
      return null;
    }
    return parsed as PendingRunMutationRecoveryRecord;
  } catch {
    return null;
  }
}

export function ProjectRunMonitorPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);
  const setRunId = useWorkspaceStore((state) => state.setRunId);

  const projectId = routeProjectId ?? storeProjectId;
  const runDetailQuery = useRunDetailQuery(projectId, runId);
  const runConfigPresetMutation = useRunConfigPresetMutation(projectId, runId);
  const rerunRunMutation = useRerunRunMutation(projectId, runId);
  const recoverRunMutation = useRecoverRunMutation(projectId, runId);
  const cancelRunMutation = useCancelRunMutation(projectId, runId);
  const audiobookPrepDashboardQuery = useAudiobookPrepDashboardQuery(projectId, runId);
  const characterAnalyticsQuery = useCharacterAnalyticsQuery(projectId, runId);
  const characterCooccurrenceGraphQuery = useCharacterCooccurrenceGraphQuery(projectId, runId);
  const tensionGraphQuery = useTensionGraphQuery(projectId, runId);
  const polarityGraphQuery = usePolarityGraphQuery(projectId, runId);
  const pipelineStageDurationsDashboardQuery = usePipelineStageDurationsDashboardQuery(projectId, runId);
  const [comparisonRunIdInput, setComparisonRunIdInput] = useState('');
  const comparisonRunId = useMemo(() => {
    const trimmed = comparisonRunIdInput.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number.parseInt(trimmed, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return null;
    }
    return parsed;
  }, [comparisonRunIdInput]);
  const runConfigDiffQuery = useRunConfigDiffQuery(projectId, runId, comparisonRunId);
  const [pendingMutationRecovery, setPendingMutationRecovery] = useState<PendingRunMutationRecoveryRecord | null>(null);
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
  const runIsActive = isRunStatusActive(runStatus);
  const isMutationRecoveryLocked = pendingMutationRecovery !== null;

  function persistPendingMutationRecovery(record: PendingRunMutationRecoveryRecord) {
    setPendingMutationRecovery(record);
    window.sessionStorage.setItem(runMutationRecoveryStorageKey, JSON.stringify(record));
  }

  function clearPendingMutationRecovery() {
    setPendingMutationRecovery(null);
    window.sessionStorage.removeItem(runMutationRecoveryStorageKey);
  }

  useEffect(() => {
    if (projectId === null) {
      clearPendingMutationRecovery();
      return;
    }
    const parsedRecord = parsePendingRunMutationRecovery(window.sessionStorage.getItem(runMutationRecoveryStorageKey));
    if (!parsedRecord) {
      clearPendingMutationRecovery();
      return;
    }
    if (parsedRecord.projectId !== projectId) {
      clearPendingMutationRecovery();
      return;
    }
    const startedAtMs = Date.parse(parsedRecord.startedAt);
    if (Number.isNaN(startedAtMs) || Date.now() - startedAtMs > runMutationRecoveryMaxAgeMs) {
      clearPendingMutationRecovery();
      return;
    }
    setPendingMutationRecovery(parsedRecord);
  }, [projectId]);

  useEffect(() => {
    if (!pendingMutationRecovery || !runDetailQuery.data) {
      return;
    }
    if (runDetailQuery.data.run_id !== pendingMutationRecovery.trackedRunId) {
      return;
    }
    if (isRunStatusTerminal(runDetailQuery.data.status)) {
      clearPendingMutationRecovery();
    }
  }, [pendingMutationRecovery, runDetailQuery.data]);

  useEffect(() => {
    if (!runIsActive && !pendingMutationRecovery) {
      return;
    }

    const refreshAllRunMonitorQueries = () => {
      void runDetailQuery.mutate();
      void audiobookPrepDashboardQuery.mutate();
      void characterAnalyticsQuery.mutate();
      void characterCooccurrenceGraphQuery.mutate();
      void tensionGraphQuery.mutate();
      void polarityGraphQuery.mutate();
      void pipelineStageDurationsDashboardQuery.mutate();
    };

    const intervalId = window.setInterval(refreshAllRunMonitorQueries, runMonitorRefreshIntervalMs);
    const handleWindowFocus = () => {
      refreshAllRunMonitorQueries();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshAllRunMonitorQueries();
      }
    };

    window.addEventListener('focus', handleWindowFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener('focus', handleWindowFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [
    runIsActive,
    pendingMutationRecovery,
    runDetailQuery,
    audiobookPrepDashboardQuery,
    characterAnalyticsQuery,
    characterCooccurrenceGraphQuery,
    tensionGraphQuery,
    polarityGraphQuery,
    pipelineStageDurationsDashboardQuery,
  ]);

  async function handleLoadRunConfigPreset() {
    if (projectId === null || runId === null) {
      return;
    }
    try {
      await runConfigPresetMutation.trigger();
    } catch {
      // errors are surfaced from runConfigPresetMutation.error in the page body
    }
  }

  async function handleExportRunConfigPreset() {
    if (projectId === null || runId === null) {
      return;
    }
    try {
      const preset = await runConfigPresetMutation.trigger();
      const blob = new Blob([JSON.stringify(preset, null, 2)], { type: 'application/json' });
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `run-config-preset-project-${projectId}-run-${runId}.json`;
      link.click();
      URL.revokeObjectURL(objectUrl);
    } catch {
      // errors are surfaced from runConfigPresetMutation.error in the page body
    }
  }

  async function handleRerunRun() {
    if (projectId === null || runId === null) {
      return;
    }
    persistPendingMutationRecovery({
      projectId,
      sourceRunId: runId,
      trackedRunId: runId,
      mutation: 'rerun',
      startedAt: new Date().toISOString(),
    });
    try {
      const rerun = await rerunRunMutation.trigger();
      setRunId(rerun.run_id);
      persistPendingMutationRecovery({
        projectId,
        sourceRunId: runId,
        trackedRunId: rerun.run_id,
        mutation: 'rerun',
        startedAt: new Date().toISOString(),
      });
    } catch {
      clearPendingMutationRecovery();
      // surfaced via mutation event bus
    }
  }

  async function handleRecoverRun() {
    if (projectId === null || runId === null) {
      return;
    }
    persistPendingMutationRecovery({
      projectId,
      sourceRunId: runId,
      trackedRunId: runId,
      mutation: 'recover',
      startedAt: new Date().toISOString(),
    });
    try {
      const recoveredRun = await recoverRunMutation.trigger();
      setRunId(recoveredRun.run_id);
      persistPendingMutationRecovery({
        projectId,
        sourceRunId: runId,
        trackedRunId: recoveredRun.run_id,
        mutation: 'recover',
        startedAt: new Date().toISOString(),
      });
    } catch {
      clearPendingMutationRecovery();
      // surfaced via mutation event bus
    }
  }

  async function handleCancelRun() {
    if (projectId === null || runId === null) {
      return;
    }
    persistPendingMutationRecovery({
      projectId,
      sourceRunId: runId,
      trackedRunId: runId,
      mutation: 'cancel',
      startedAt: new Date().toISOString(),
    });
    try {
      const cancelledRun = await cancelRunMutation.trigger();
      setRunId(cancelledRun.run_id);
      persistPendingMutationRecovery({
        projectId,
        sourceRunId: runId,
        trackedRunId: cancelledRun.run_id,
        mutation: 'cancel',
        startedAt: new Date().toISOString(),
      });
    } catch {
      clearPendingMutationRecovery();
      // surfaced via mutation event bus
    }
  }

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
              disabled={runId === null || rerunRunMutation.isMutating || isMutationRecoveryLocked}
              onClick={handleRerunRun}
              variant="outline"
            >
              {rerunRunMutation.isMutating ? 'Rerunning...' : 'Rerun run'}
            </Button>
            <Button
              disabled={runId === null || recoverRunMutation.isMutating || isMutationRecoveryLocked}
              onClick={handleRecoverRun}
              variant="outline"
            >
              {recoverRunMutation.isMutating ? 'Recovering...' : 'Recover run'}
            </Button>
            <Button
              disabled={runId === null || cancelRunMutation.isMutating || isMutationRecoveryLocked}
              onClick={handleCancelRun}
              variant="outline"
            >
              {cancelRunMutation.isMutating ? 'Cancelling...' : 'Cancel run'}
            </Button>
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
              <p data-testid="run-monitor-refresh-state">
                Refresh loop: <strong className="text-foreground">{runIsActive || pendingMutationRecovery ? 'active' : 'idle'}</strong>
              </p>
            </div>

            {pendingMutationRecovery ? (
              <Alert data-testid="run-monitor-mutation-recovery-banner" className="border-primary/40">
                <AlertTitle>Recovering in-flight run action</AlertTitle>
                <AlertDescription>
                  Restored pending <strong className="text-foreground">{pendingMutationRecovery.mutation}</strong> action.
                  Monitoring run <strong className="text-foreground">#{pendingMutationRecovery.trackedRunId}</strong> until
                  terminal state.
                </AlertDescription>
              </Alert>
            ) : null}

            {runDetailQuery.isLoading ? <p>Loading run detail...</p> : null}
            {runDetailQuery.error ? <p className="text-destructive">{runDetailQuery.error.message}</p> : null}
            {runConfigPresetMutation.error ? <p className="text-destructive">{runConfigPresetMutation.error.message}</p> : null}
            {rerunRunMutation.error ? <p className="text-destructive">{rerunRunMutation.error.message}</p> : null}
            {recoverRunMutation.error ? <p className="text-destructive">{recoverRunMutation.error.message}</p> : null}
            {cancelRunMutation.error ? <p className="text-destructive">{cancelRunMutation.error.message}</p> : null}

            <div className="space-y-2 rounded-xl border border-border/60 bg-background/60 p-3">
              <p className="font-medium text-foreground">Run Config Preset Panel</p>
              <p className="text-xs text-muted-foreground">
                Load and review the backend run config preset for this run before exporting it.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={runId === null || runConfigPresetMutation.isMutating}
                  onClick={handleLoadRunConfigPreset}
                  size="sm"
                  variant="outline"
                >
                  {runConfigPresetMutation.isMutating ? 'Loading preset...' : 'Load run config preset'}
                </Button>
                <Button
                  disabled={runId === null || runConfigPresetMutation.isMutating}
                  onClick={handleExportRunConfigPreset}
                  size="sm"
                  variant="outline"
                >
                  Export preset JSON
                </Button>
              </div>
              {runConfigPresetMutation.data ? (
                <pre className="max-h-56 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
                  {JSON.stringify(runConfigPresetMutation.data, null, 2)}
                </pre>
              ) : (
                <p className="text-xs text-muted-foreground">No preset loaded yet.</p>
              )}
            </div>

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

      <Card>
        <CardHeader>
          <CardTitle>Pipeline Stage Durations Dashboard</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {pipelineStageDurationsDashboardQuery.isLoading ? <p>Loading stage duration metrics...</p> : null}
          {pipelineStageDurationsDashboardQuery.error ? (
            <p className="text-destructive">{pipelineStageDurationsDashboardQuery.error.message}</p>
          ) : null}
          {pipelineStageDurationsDashboardQuery.data ? (
            <pre className="max-h-64 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
              {JSON.stringify(pipelineStageDurationsDashboardQuery.data, null, 2)}
            </pre>
          ) : (
            <p>No stage duration metrics yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Audiobook Prep Dashboard</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {audiobookPrepDashboardQuery.isLoading ? <p>Loading audiobook prep metrics...</p> : null}
          {audiobookPrepDashboardQuery.error ? <p className="text-destructive">{audiobookPrepDashboardQuery.error.message}</p> : null}
          {audiobookPrepDashboardQuery.data ? (
            <pre className="max-h-64 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
              {JSON.stringify(audiobookPrepDashboardQuery.data, null, 2)}
            </pre>
          ) : (
            <p>No audiobook prep metrics yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Character Analytics Dashboard</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {characterAnalyticsQuery.isLoading ? <p>Loading character analytics...</p> : null}
          {characterAnalyticsQuery.error ? <p className="text-destructive">{characterAnalyticsQuery.error.message}</p> : null}
          {characterAnalyticsQuery.data ? (
            <pre className="max-h-64 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
              {JSON.stringify(characterAnalyticsQuery.data, null, 2)}
            </pre>
          ) : (
            <p>No character analytics yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Character Co-occurrence Graph</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {characterCooccurrenceGraphQuery.isLoading ? <p>Loading co-occurrence graph...</p> : null}
          {characterCooccurrenceGraphQuery.error ? (
            <p className="text-destructive">{characterCooccurrenceGraphQuery.error.message}</p>
          ) : null}
          {characterCooccurrenceGraphQuery.data ? (
            <pre className="max-h-64 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
              {JSON.stringify(characterCooccurrenceGraphQuery.data, null, 2)}
            </pre>
          ) : (
            <p>No co-occurrence graph yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tension Graph</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {tensionGraphQuery.isLoading ? <p>Loading tension graph...</p> : null}
          {tensionGraphQuery.error ? <p className="text-destructive">{tensionGraphQuery.error.message}</p> : null}
          {tensionGraphQuery.data ? (
            <pre className="max-h-64 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
              {JSON.stringify(tensionGraphQuery.data, null, 2)}
            </pre>
          ) : (
            <p>No tension graph yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Polarity Graph</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {polarityGraphQuery.isLoading ? <p>Loading polarity graph...</p> : null}
          {polarityGraphQuery.error ? <p className="text-destructive">{polarityGraphQuery.error.message}</p> : null}
          {polarityGraphQuery.data ? (
            <pre className="max-h-64 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
              {JSON.stringify(polarityGraphQuery.data, null, 2)}
            </pre>
          ) : (
            <p>No polarity graph yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Run Config Diff Viewer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>Compare this run configuration against another run ID from the same project.</p>
          <div className="max-w-sm">
            <Input
              value={comparisonRunIdInput}
              onChange={(event) => setComparisonRunIdInput(event.target.value)}
              placeholder="Enter comparison run ID"
              inputMode="numeric"
            />
          </div>
          {comparisonRunIdInput.trim() && comparisonRunId === null ? (
            <p className="text-destructive">Enter a valid positive run ID to load a config diff.</p>
          ) : null}
          {runConfigDiffQuery.isLoading ? <p>Loading config diff...</p> : null}
          {runConfigDiffQuery.error ? <p className="text-destructive">{runConfigDiffQuery.error.message}</p> : null}
          {runConfigDiffQuery.data ? (
            <div className="space-y-3">
              <p>
                Compared run <strong className="text-foreground">{runConfigDiffQuery.data.base_run_id}</strong> to run{' '}
                <strong className="text-foreground">{runConfigDiffQuery.data.target_run_id}</strong>.
              </p>
              <p>
                Schema versions: base{' '}
                <strong className="text-foreground">{runConfigDiffQuery.data.base_config_schema_version}</strong>, target{' '}
                <strong className="text-foreground">{runConfigDiffQuery.data.target_config_schema_version}</strong>.
              </p>
              {runConfigDiffQuery.data.is_identical ? (
                <p>No configuration differences detected.</p>
              ) : (
                <p>
                  Changed fields: <strong className="text-foreground">{runConfigDiffQuery.data.changed_fields.length}</strong>
                </p>
              )}

              {runConfigDiffQuery.data.changed_fields.length > 0 ? (
                <div className="space-y-2">
                  {runConfigDiffQuery.data.changed_fields.map((entry) => (
                    <div key={entry.field} className="rounded-xl bg-background/70 px-3 py-2">
                      <p className="font-medium text-foreground">{entry.field}</p>
                      <p className="text-xs">
                        {JSON.stringify(entry.base_value)} → {JSON.stringify(entry.target_value)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}

              {runConfigDiffQuery.data.base_only_fields.length > 0 ? (
                <p>
                  Base-only fields: <strong className="text-foreground">{runConfigDiffQuery.data.base_only_fields.join(', ')}</strong>
                </p>
              ) : null}
              {runConfigDiffQuery.data.target_only_fields.length > 0 ? (
                <p>
                  Target-only fields: <strong className="text-foreground">{runConfigDiffQuery.data.target_only_fields.join(', ')}</strong>
                </p>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
