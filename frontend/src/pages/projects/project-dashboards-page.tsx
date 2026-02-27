import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  useTensionGraphQuery,
  usePolarityGraphQuery,
  useCharacterAnalyticsQuery,
  useCharacterCooccurrenceGraphQuery,
  useAudiobookPrepDashboardQuery,
  usePipelineStageDurationsDashboardQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

function ChartPanel({ title, description, children, isLoading }: { title: string; description?: string; children?: React.ReactNode; isLoading?: boolean }) {
  return (
    <div className="rounded-xl border border-white/10 bg-card p-4">
      <p className="mb-0.5 text-sm font-semibold text-foreground">{title}</p>
      {description && <p className="mb-3 text-xs text-muted-foreground">{description}</p>}
      {!description && <div className="mb-3" />}
      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <div className="h-32 w-full animate-pulse rounded-lg bg-white/5" />
        </div>
      ) : (
        <div className="min-h-40">{children}</div>
      )}
    </div>
  );
}

function SimpleLinePreview({ data, color = '#60a5fa' }: { data: number[]; color?: string }) {
  if (!data.length) return <p className="py-8 text-center text-xs text-muted-foreground">No data</p>;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 100, h = 60;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`).join(' ');
  return (
    <svg className="w-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <polyline fill="none" points={pts} stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function BarChart({ data }: { data: Array<{ label: string; value: number; total: number }> }) {
  if (!data.length) return <p className="py-8 text-center text-xs text-muted-foreground">No data</p>;
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label}>
          <div className="mb-0.5 flex items-center justify-between text-xs">
            <span className="text-foreground truncate max-w-[60%]">{d.label}</span>
            <span className="text-muted-foreground">{d.value.toLocaleString()}</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/5">
            <div
              className="h-1.5 rounded-full bg-foreground/30 transition-all"
              style={{ width: `${Math.min(100, (d.value / (d.total || 1)) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ProjectDashboardsPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const storeRunId = useWorkspaceStore((state) => state.runId);
  const projectId = routeProjectId ?? storeProjectId;
  const [runIdInput, setRunIdInput] = useState(storeRunId !== null ? String(storeRunId) : '');
  const [activeRunId, setActiveRunId] = useState<number | null>(storeRunId);

  const tensionQuery = useTensionGraphQuery(projectId, activeRunId);
  const polarityQuery = usePolarityGraphQuery(projectId, activeRunId);
  const analyticsQuery = useCharacterAnalyticsQuery(projectId, activeRunId);
  const cooccurrenceQuery = useCharacterCooccurrenceGraphQuery(projectId, activeRunId);
  const audiobookQuery = useAudiobookPrepDashboardQuery(projectId, activeRunId);
  const stageDurationsQuery = usePipelineStageDurationsDashboardQuery(projectId, activeRunId);

  function loadRun() {
    const n = Number(runIdInput);
    if (!Number.isInteger(n) || n <= 0) { toast.error('Enter a valid run ID'); return; }
    setActiveRunId(n);
  }

  const audiobookData = audiobookQuery.data;
  const isAudiobookReady = audiobookData?.export_readiness?.is_ready;
  const stageData = stageDurationsQuery.data;
  const totalMs = stageData?.total_duration_ms ?? 1;

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Analytics`}
      title="Analytics"
      description="Narrative tension, sentiment, character analysis, and pipeline performance across your manuscript."
    >
      <div className="flex items-center gap-3">
        <Input
          className="w-36 font-mono"
          data-testid="analytics-run-id-input"
          onChange={(e) => setRunIdInput(e.target.value)}
          placeholder="Run ID"
          type="number"
          value={runIdInput}
        />
        <Button onClick={loadRun} size="sm" variant="outline">Load run</Button>
        {activeRunId && <span className="text-sm text-muted-foreground">Run #{activeRunId}</span>}
      </div>

      {activeRunId === null ? (
        <div className="rounded-xl border border-white/10 bg-card p-10 text-center">
          <p className="text-sm text-muted-foreground">Load a run to view analytics.</p>
        </div>
      ) : (
        <div className="space-y-4" data-testid="analytics-grid">
          {/* Audiobook prep readiness */}
          {(audiobookQuery.isLoading || audiobookData) && (
            <div className={cn(
              'rounded-xl border p-4',
              audiobookQuery.isLoading ? 'border-white/10 bg-card' :
              isAudiobookReady ? 'border-green-400/20 bg-green-400/5' : 'border-amber-400/20 bg-amber-400/5',
            )} data-testid="audiobook-prep-dashboard">
              {audiobookQuery.isLoading ? (
                <div className="h-6 w-48 animate-pulse rounded bg-white/5" />
              ) : audiobookData && (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    {isAudiobookReady ? (
                      <CheckCircle2 className="text-green-400 shrink-0" size={16} />
                    ) : (
                      <AlertTriangle className="text-amber-400 shrink-0" size={16} />
                    )}
                    <p className={cn('text-sm font-semibold', isAudiobookReady ? 'text-green-400' : 'text-amber-400')}>
                      Audiobook Export {isAudiobookReady ? 'Ready' : 'Not Ready'}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                    <span>{audiobookData.unresolved_speaker_count} unresolved speakers</span>
                    <span>{audiobookData.unresolved_voice_mapping_count} unresolved voice mappings</span>
                    <span>{audiobookData.low_confidence_region_count} low confidence regions</span>
                  </div>
                  {audiobookData.export_readiness.blocking_reasons.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {audiobookData.export_readiness.blocking_reasons.map((r, i) => (
                        <li className="flex items-start gap-1.5 text-xs text-amber-400/80" key={i}>
                          <XCircle size={11} className="mt-0.5 shrink-0" />
                          {r}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
          )}

          {/* Main charts 2-col grid */}
          <div className="grid gap-4 sm:grid-cols-2">
            <ChartPanel title="Tension Graph" description="Narrative tension over segments">
              <SimpleLinePreview
                color="oklch(0.623 0.214 259.815)"
                data={tensionQuery.data?.points?.map((p) => p.smoothed_tension) ?? []}
              />
            </ChartPanel>

            <ChartPanel title="Polarity Graph" description="Sentiment valence over segments">
              <SimpleLinePreview
                color="oklch(0.722 0.181 65.403)"
                data={polarityQuery.data?.points?.map((p) => p.rolling_mean_valence) ?? []}
              />
            </ChartPanel>

            <ChartPanel title="Character Analytics" description="Dialogue line count per character">
              {analyticsQuery.data && Object.keys(analyticsQuery.data.character_dialogue_line_counts ?? {}).length > 0 ? (
                <BarChart
                  data={Object.entries(analyticsQuery.data.character_dialogue_line_counts)
                    .sort(([, a], [, b]) => Number(b) - Number(a))
                    .slice(0, 8)
                    .map(([name, count]) => ({
                      label: name,
                      value: Number(count),
                      total: Math.max(...Object.values(analyticsQuery.data!.character_dialogue_line_counts).map(Number)),
                    }))}
                />
              ) : (
                <p className="py-8 text-center text-xs text-muted-foreground">No character data</p>
              )}
            </ChartPanel>

            <ChartPanel title="Character Co-occurrence" description="How often characters appear together">
              {cooccurrenceQuery.data?.graph?.edges?.length ? (
                <BarChart
                  data={cooccurrenceQuery.data.graph.edges.slice(0, 8).map((edge) => ({
                    label: `${edge.source} × ${edge.target}`,
                    value: Number(edge.weight),
                    total: Math.max(...(cooccurrenceQuery.data?.graph?.edges?.map((e) => Number(e.weight)) ?? [1])),
                  }))}
                />
              ) : (
                <p className="py-8 text-center text-xs text-muted-foreground">No co-occurrence data</p>
              )}
            </ChartPanel>
          </div>

          {/* Pipeline stage durations */}
          {(stageDurationsQuery.isLoading || stageData) && (
            <div className="rounded-xl border border-white/10 bg-card p-4" data-testid="stage-durations-panel">
              <p className="mb-0.5 text-sm font-semibold text-foreground">Pipeline Stage Durations</p>
              <p className="mb-3 text-xs text-muted-foreground">
                {stageData ? `Total: ${(totalMs / 1000).toFixed(1)}s · ${stageData.stage_count} stages` : ''}
                {stageData?.slowest_stage_name ? ` · Slowest: ${stageData.slowest_stage_name} (${((stageData.slowest_stage_duration_ms ?? 0) / 1000).toFixed(1)}s)` : ''}
              </p>
              {stageDurationsQuery.isLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3, 4].map((i) => <div className="h-6 animate-pulse rounded bg-white/5" key={i} />)}
                </div>
              ) : stageData && stageData.stages.length > 0 ? (
                <div className="space-y-2">
                  {stageData.stages.sort((a, b) => b.duration_ms - a.duration_ms).map((stage) => (
                    <div key={stage.stage_name}>
                      <div className="mb-0.5 flex items-center justify-between text-xs">
                        <span className="text-foreground">{stage.stage_name}</span>
                        <span className="text-muted-foreground">
                          {(stage.duration_ms / 1000).toFixed(2)}s · {(stage.share_of_total * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/5">
                        <div
                          className="h-1.5 rounded-full bg-foreground/40 transition-all"
                          style={{ width: `${stage.share_of_total * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-4 text-center text-xs text-muted-foreground">No stage data available</p>
              )}
            </div>
          )}
        </div>
      )}
    </WorkflowPageShell>
  );
}
