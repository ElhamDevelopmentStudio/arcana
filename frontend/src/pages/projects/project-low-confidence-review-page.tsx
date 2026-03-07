import { useParams } from 'react-router-dom';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectLowConfidenceReviewPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const storeRunId = useWorkspaceStore((state) => state.runId);
  const projectId = routeProjectId ?? storeProjectId;

  const exportQuery = useExportPayloadQuery(projectId, storeRunId);
  const segments = (exportQuery.data?.segments ?? []) as Array<{
    segment_id?: string;
    original_text?: string;
    speaker?: string;
    speaker_confidence?: string;
    emotion?: string;
    emotion_confidence?: string;
  }>;
  const lowConfidence = segments.filter(
    (s) => s.speaker_confidence === 'low' || s.emotion_confidence === 'low',
  );

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Low-Confidence Review`}
      title="Low-Confidence Review"
      description="Segments with uncertain speaker or emotion assignments that may need manual correction."
    >
      {exportQuery.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div className="h-14 animate-pulse rounded-lg border border-white/5 bg-card" key={i} />
          ))}
        </div>
      ) : lowConfidence.length === 0 ? (
        <div className="rounded-xl border border-white/10 bg-card p-10 text-center" data-testid="low-confidence-empty">
          <p className="text-sm font-medium text-foreground">No low-confidence segments</p>
          <p className="mt-1 text-sm text-muted-foreground">All outputs meet the confidence threshold.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-white/10 bg-card overflow-hidden" data-testid="low-confidence-table">
          <div className="border-b border-white/10 px-4 py-2.5">
            <p className="text-xs text-muted-foreground">{lowConfidence.length} segments require attention</p>
          </div>
          <div className="divide-y divide-white/5">
            {lowConfidence.map((seg, i) => (
              <div className="flex items-start gap-4 px-4 py-3" key={seg.segment_id ?? i}>
                <p className="flex-1 line-clamp-2 text-sm text-foreground">{seg.original_text}</p>
                <div className="shrink-0 space-y-1 text-right">
                  {seg.speaker && (
                    <div className="flex items-center justify-end gap-1.5">
                      <span className="text-xs text-muted-foreground">Speaker</span>
                      <span className="text-xs font-medium text-foreground">{seg.speaker}</span>
                      {seg.speaker_confidence === 'low' && (
                        <span className="rounded-full bg-red-400/10 px-1.5 py-0.5 text-xs text-red-400">low</span>
                      )}
                    </div>
                  )}
                  {seg.emotion && (
                    <div className="flex items-center justify-end gap-1.5">
                      <span className="text-xs text-muted-foreground">Emotion</span>
                      <span className="text-xs font-medium capitalize text-foreground">{seg.emotion}</span>
                      {seg.emotion_confidence === 'low' && (
                        <span className="rounded-full bg-red-400/10 px-1.5 py-0.5 text-xs text-red-400">low</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </WorkflowPageShell>
  );
}
