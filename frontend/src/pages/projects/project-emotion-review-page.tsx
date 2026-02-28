import { useParams } from 'react-router-dom';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';

const CONFIDENCE_COLOR: Record<string, string> = {
  high: 'bg-green-400/10 text-green-400',
  medium: 'bg-amber-400/10 text-amber-400',
  low: 'bg-red-400/10 text-red-400',
};

export function ProjectEmotionReviewPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const storeRunId = useWorkspaceStore((state) => state.runId);
  const projectId = routeProjectId ?? storeProjectId;

  const exportQuery = useExportPayloadQuery(projectId, storeRunId);
  const segments = (exportQuery.data?.segments ?? []) as Array<{
    segment_id?: string;
    original_text?: string;
    emotion?: string;
    emotion_confidence?: string;
  }>;
  const lowConfidence = segments.filter((s) => s.emotion_confidence === 'low');

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Emotion Review`}
      title="Emotion Review"
      description="Review low-confidence emotion tags before export."
    >
      {exportQuery.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="h-14 animate-pulse rounded-lg border border-white/5 bg-card" key={i} />
          ))}
        </div>
      ) : lowConfidence.length === 0 ? (
        <div className="rounded-xl border border-white/10 bg-card p-10 text-center" data-testid="emotion-review-empty">
          <p className="text-sm font-medium text-foreground">No low-confidence emotions</p>
          <p className="mt-1 text-sm text-muted-foreground">All emotion tags passed confidence thresholds.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-white/10 bg-card overflow-hidden" data-testid="emotion-review-table">
          <div className="border-b border-white/10 px-4 py-2.5">
            <p className="text-xs text-muted-foreground">{lowConfidence.length} segments to review</p>
          </div>
          <div className="divide-y divide-white/5">
            {lowConfidence.map((seg, i) => (
              <div className="flex items-start gap-4 px-4 py-3" key={seg.segment_id ?? i}>
                <p className="flex-1 line-clamp-2 text-sm text-foreground">{seg.original_text}</p>
                <div className="shrink-0 text-right space-y-1">
                  <p className="text-sm font-medium text-foreground capitalize">{seg.emotion ?? '—'}</p>
                  <span className={cn('inline-flex rounded-full px-2 py-0.5 text-xs font-medium', CONFIDENCE_COLOR[seg.emotion_confidence ?? 'low'])}>
                    {seg.emotion_confidence ?? 'low'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </WorkflowPageShell>
  );
}
