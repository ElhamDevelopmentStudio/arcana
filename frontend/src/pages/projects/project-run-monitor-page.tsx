import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { CheckCircle2, XCircle, Loader2, Circle, RotateCcw, StopCircle, RefreshCw, Download } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  useCancelRunMutation,
  useRecoverRunMutation,
  useRerunRunMutation,
  useRunDetailQuery,
  useRunConfigPresetMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';
import { useJobNotificationStore } from '@/features/workflow/state/job-notification-store';

const REFRESH_INTERVAL_MS = 4000;

function llmCallIcon(success: boolean) {
  if (success) return <CheckCircle2 className="text-green-400" size={14} />;
  return <XCircle className="text-red-400" size={14} />;
}

function isActiveStatus(status: string | null | undefined) {
  return status === 'running' || status === 'queued';
}

const STATUS_BADGE: Record<string, string> = {
  running: 'bg-amber-400/10 text-amber-400',
  queued: 'bg-amber-400/10 text-amber-400',
  completed: 'bg-green-400/10 text-green-400',
  failed: 'bg-red-400/10 text-red-400',
  cancelled: 'bg-white/10 text-muted-foreground',
};

export function ProjectRunMonitorPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const [searchParams] = useSearchParams();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const storeRunId = useWorkspaceStore((state) => state.runId);
  const setRunId = useWorkspaceStore((state) => state.setRunId);
  const registerJob = useJobNotificationStore((state) => state.registerJob);

  const projectId = routeProjectId ?? storeProjectId;
  const urlRunId = searchParams.get('run_id') ? Number(searchParams.get('run_id')) : null;
  const [activeRunId, setActiveRunId] = useState<number | null>(urlRunId ?? storeRunId);
  const [manualRunId, setManualRunId] = useState('');

  const runDetailQuery = useRunDetailQuery(projectId, activeRunId);
  const cancelMutation = useCancelRunMutation(projectId, activeRunId);
  const rerunMutation = useRerunRunMutation(projectId, activeRunId);
  const recoverMutation = useRecoverRunMutation(projectId, activeRunId);
  const configPresetMutation = useRunConfigPresetMutation(projectId, activeRunId);

  const runDetail = runDetailQuery.data;
  const runStatus = runDetail?.status ?? null;
  const isActive = isActiveStatus(runStatus);
  const isBusy = cancelMutation.isMutating || rerunMutation.isMutating || recoverMutation.isMutating;

  async function handleDownloadPreset() {
    try {
      const preset = await configPresetMutation.trigger();
      const blob = new Blob([JSON.stringify(preset, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `run-${activeRunId ?? 'unknown'}-config-preset.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to download config preset');
    }
  }

  useEffect(() => {
    if (!isActive) return;
    const id = window.setInterval(() => void runDetailQuery.mutate(), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [isActive, runDetailQuery]);

  useEffect(() => {
    if (projectId === null || activeRunId === null || !runStatus) {
      return;
    }
    if (!isActiveStatus(runStatus)) {
      return;
    }
    registerJob({
      type: 'pipeline',
      projectId,
      jobId: String(activeRunId),
      status: runStatus,
    });
  }, [activeRunId, projectId, registerJob, runStatus]);

  const llmCalls = runDetail?.llm_calls ?? [];
  const successfulCalls = llmCalls.filter((c) => c.success).length;
  const changelogEntries = runDetail?.changelog_entries ?? [];

  async function handleCancel() {
    try {
      await cancelMutation.trigger();
      toast.success('Run cancelled.');
      await runDetailQuery.mutate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Cancel failed');
    }
  }

  async function handleRerun() {
    try {
      const res = await rerunMutation.trigger();
      setRunId(res.run_id);
      setActiveRunId(res.run_id);
      if (projectId !== null) {
        registerJob({
          type: 'pipeline',
          projectId,
          jobId: String(res.run_id),
          status: res.status,
        });
      }
      toast.success(`Rerun #${res.run_id} started.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Rerun failed');
    }
  }

  async function handleRecover() {
    try {
      const res = await recoverMutation.trigger();
      setRunId(res.run_id);
      setActiveRunId(res.run_id);
      if (projectId !== null) {
        registerJob({
          type: 'pipeline',
          projectId,
          jobId: String(res.run_id),
          status: res.status,
        });
      }
      toast.success(`Recovery run #${res.run_id} started.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Recovery failed');
    }
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Runs`}
      title="Run Monitor"
      description="Track run progress, LLM call metrics, and pipeline changelog."
    >
      {/* Run ID picker */}
      <div className="flex items-center gap-3">
        <Input
          className="w-36 font-mono"
          data-testid="run-id-input"
          onChange={(e) => setManualRunId(e.target.value)}
          placeholder="Run ID"
          type="number"
          value={manualRunId}
        />
        <Button
          onClick={() => {
            const n = Number(manualRunId);
            if (!Number.isInteger(n) || n <= 0) { toast.error('Enter a valid run ID'); return; }
            setActiveRunId(n);
            setRunId(n);
            setManualRunId('');
          }}
          size="sm"
          variant="outline"
        >
          Load run
        </Button>
        {activeRunId && (
          <span className="font-mono text-sm text-muted-foreground">Run #{activeRunId}</span>
        )}
      </div>

      {activeRunId === null ? (
        <div className="rounded-xl border border-white/10 bg-card p-8 text-center" data-testid="run-monitor-no-run">
          <p className="text-sm text-muted-foreground">No run selected. Enter a run ID above or start a run from Pipeline Setup.</p>
          <Button
            className="mt-4"
            onClick={() => projectId !== null && navigate(`/projects/${projectId}/pipeline-setup`)}
            size="sm"
            variant="outline"
          >
            Go to Pipeline Setup
          </Button>
        </div>
      ) : runDetailQuery.isLoading && !runDetail ? (
        <div className="h-10 w-full animate-pulse rounded-lg bg-card" data-testid="run-monitor-loading" />
      ) : runDetailQuery.error ? (
        <div className="rounded-xl border border-white/10 bg-card p-6 text-center" data-testid="run-monitor-error">
          <p className="text-sm text-muted-foreground">Unable to load run details.</p>
          <Button className="mt-3" onClick={() => void runDetailQuery.mutate()} size="sm" variant="outline">Retry</Button>
        </div>
      ) : (
        <div className="space-y-4" data-testid="run-monitor-detail">
          {/* Header */}
          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-white/10 bg-card p-4">
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                {runStatus === 'running' && <Loader2 className="animate-spin text-amber-400" size={14} />}
                <span className="font-mono text-sm font-semibold text-foreground">Run #{runDetail?.run_id}</span>
                {runStatus && (
                  <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', STATUS_BADGE[runStatus] ?? 'bg-white/10 text-muted-foreground')}>
                    {runStatus}
                  </span>
                )}
                {isActive && (
                  <button
                    className="ml-1 text-muted-foreground hover:text-foreground"
                    onClick={() => void runDetailQuery.mutate()}
                    type="button"
                  >
                    <RefreshCw size={13} />
                  </button>
                )}
              </div>
              {runDetail?.started_at && (
                <p className="text-xs text-muted-foreground">
                  Started {new Date(runDetail.started_at).toLocaleString()}
                  {runDetail.finished_at ? ` · Finished ${new Date(runDetail.finished_at).toLocaleString()}` : ''}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                {runDetail?.segment_count ?? 0} segments · {llmCalls.length} LLM calls ({successfulCalls} ok)
              </p>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              {isActive && (
                <Button
                  data-testid="cancel-run-button"
                  disabled={isBusy}
                  onClick={() => void handleCancel()}
                  size="sm"
                  variant="destructive"
                >
                  <StopCircle size={13} />
                  {cancelMutation.isMutating ? 'Cancelling…' : 'Cancel'}
                </Button>
              )}
              {(runStatus === 'failed' || runStatus === 'completed') && (
                <>
                  {runStatus === 'failed' && (
                    <Button
                      data-testid="recover-run-button"
                      disabled={isBusy}
                      onClick={() => void handleRecover()}
                      size="sm"
                      variant="outline"
                    >
                      <RefreshCw size={13} />
                      {recoverMutation.isMutating ? 'Recovering…' : 'Recover'}
                    </Button>
                  )}
                  <Button
                    data-testid="rerun-button"
                    disabled={isBusy}
                    onClick={() => void handleRerun()}
                    size="sm"
                    variant="outline"
                  >
                    <RotateCcw size={13} />
                    {rerunMutation.isMutating ? 'Rerunning…' : 'Rerun'}
                  </Button>
                </>
              )}
              <Button
                data-testid="download-config-preset-button"
                disabled={configPresetMutation.isMutating || !activeRunId}
                onClick={() => void handleDownloadPreset()}
                size="sm"
                variant="outline"
                title="Download run config preset as JSON"
              >
                <Download size={13} />
                {configPresetMutation.isMutating ? 'Exporting…' : 'Config'}
              </Button>
            </div>
          </div>

          {/* LLM Calls */}
          {llmCalls.length > 0 && (
            <div className="rounded-xl border border-white/10 bg-card overflow-hidden" data-testid="run-llm-calls">
              <div className="border-b border-white/10 px-4 py-2.5">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/60">LLM Calls</p>
              </div>
              <div className="divide-y divide-white/5 max-h-48 overflow-y-auto">
                {llmCalls.map((call) => (
                  <div className="flex items-center gap-3 px-4 py-2.5 text-xs" key={call.id}>
                    {llmCallIcon(call.success)}
                    <span className="text-foreground">{call.task_type}</span>
                    <span className="text-muted-foreground">{call.provider}</span>
                    {call.is_cache_hit && (
                      <span className="rounded-full bg-blue-400/10 px-1.5 py-0.5 text-xs text-blue-400">cache hit</span>
                    )}
                    <span className="ml-auto text-muted-foreground">×{call.request_count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Changelog */}
          {changelogEntries.length > 0 && (
            <div className="rounded-xl border border-white/10 bg-card overflow-hidden" data-testid="run-changelog">
              <div className="border-b border-white/10 px-4 py-2.5">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/60">Changelog</p>
              </div>
              <div className="divide-y divide-white/5 max-h-60 overflow-y-auto">
                {changelogEntries.map((entry) => (
                  <div className="flex items-start gap-3 px-4 py-2.5 text-xs" key={entry.id}>
                    <Circle className="mt-0.5 shrink-0 text-muted-foreground/40" size={6} />
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-foreground">{entry.event_type}</span>
                      {entry.event_message && (
                        <p className="mt-0.5 text-muted-foreground">{entry.event_message}</p>
                      )}
                    </div>
                    <span className="shrink-0 text-muted-foreground">{new Date(entry.created_at).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </WorkflowPageShell>
  );
}
