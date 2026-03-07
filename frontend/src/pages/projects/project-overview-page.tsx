import { useNavigate, useParams } from 'react-router-dom';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { Button } from '@/components/ui/button';
import { useProjectDetailQuery, useProjectWorkspaceSummaryQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
      {sub ? <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

const STATUS_COLOR: Record<string, string> = {
  completed: 'text-green-400',
  running: 'text-amber-400',
  failed: 'text-red-400',
  queued: 'text-amber-400',
};

export function ProjectOverviewPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;
  const detailQuery = useProjectDetailQuery(projectId);
  const summaryQuery = useProjectWorkspaceSummaryQuery(projectId);

  const detail = detailQuery.data;
  const summary = summaryQuery.data;
  const isSetupComplete = summary?.is_setup_complete ?? false;
  const lastRunStatus = summary?.last_run_status ?? null;

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Overview`}
      title={detail?.title ?? `Project #${projectId ?? '—'}`}
      description={detail?.description ?? undefined}
      action={
        !isSetupComplete && projectId !== null ? (
          <Button
            data-testid="project-overview-open-setup"
            onClick={() => navigate(`/projects/${projectId}/setup`)}
          >
            Continue Setup
          </Button>
        ) : projectId !== null ? (
          <Button onClick={() => navigate(`/projects/${projectId}/runs`)}>
            View Runs
          </Button>
        ) : undefined
      }
    >
      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="project-overview-ready">
        <StatCard
          label="Chapters"
          value={summary?.chapters_count ?? 0}
        />
        <StatCard
          label="Characters"
          value={summary?.characters_count ?? 0}
        />
        <StatCard
          label="Runs"
          value={summary?.runs_total_count ?? 0}
          sub={`${summary?.runs_completed_count ?? 0} completed · ${summary?.runs_failed_count ?? 0} failed`}
        />
        <div className="rounded-xl border border-white/10 bg-card p-4">
          <p className="text-xs text-muted-foreground">Last Run</p>
          <p className={cn('mt-1 text-2xl font-bold', lastRunStatus ? STATUS_COLOR[lastRunStatus] : 'text-muted-foreground')}>
            {lastRunStatus ?? 'none'}
          </p>
        </div>
      </div>

      {/* Project details */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-card p-5">
          <p className="mb-3 text-sm font-semibold text-foreground">Project Details</p>
          <dl className="space-y-2 text-sm">
            {[
              { label: 'ID', value: detail?.project_id ?? projectId },
              { label: 'Mode', value: detail?.selected_mode ?? 'not set' },
              { label: 'Lifecycle', value: detail?.lifecycle_state ?? 'draft' },
              { label: 'Next action', value: detail?.next_required_action ?? 'none' },
              { label: 'LLM', value: detail?.llm_enabled ? 'enabled' : 'disabled' },
              { label: 'Character map', value: detail?.character_map_finalized ? 'finalized' : 'pending' },
            ].map(({ label, value }) => (
              <div className="flex items-baseline gap-2" key={label}>
                <dt className="w-28 shrink-0 text-muted-foreground">{label}</dt>
                <dd className="text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rounded-xl border border-white/10 bg-card p-5">
          <p className="mb-3 text-sm font-semibold text-foreground">Setup Status</p>
          <div className="space-y-2 text-sm">
            {[
              { label: 'Voice mappings', value: summary?.voice_mappings_count ?? 0 },
              { label: 'Last export', value: summary?.last_export_at ? new Date(summary.last_export_at).toLocaleDateString() : 'never' },
            ].map(({ label, value }) => (
              <div className="flex items-baseline gap-2" key={label}>
                <span className="w-32 shrink-0 text-muted-foreground">{label}</span>
                <span className="text-foreground">{value}</span>
              </div>
            ))}
            <div className="mt-3">
              <span className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
                isSetupComplete ? 'bg-green-400/10 text-green-400' : 'bg-amber-400/10 text-amber-400',
              )}>
                <span className="size-1.5 rounded-full bg-current" />
                {isSetupComplete ? 'Setup complete' : 'Setup in progress'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </WorkflowPageShell>
  );
}
