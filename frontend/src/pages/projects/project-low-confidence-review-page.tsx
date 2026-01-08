import { useMemo, useState } from 'react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { ChevronRight, CircleDashed, ListChecks, RefreshCcw, SearchX, ShieldAlert } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

type LowConfidenceReviewSegment = {
  segment_id: string;
  chapter_id: number | null;
  original_text: string;
  type_state: string;
  type_confidence: number | null;
  speaker_state: string;
  speaker_confidence: number | null;
  emotion_state: string;
  emotion_confidence: number | null;
  tension_state: string;
  tension_confidence: number | null;
  dominance_state: string;
  dominance_confidence: number | null;
  summary_state: string;
  summary_confidence: number | null;
  review_reasons: string[];
  is_review_candidate: boolean;
  evidence_summary: string;
};

const LOW_CONFIDENCE_THRESHOLD = 0.8;

function toStringValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'n/a';
  }
  if (typeof value === 'string') {
    return value.trim() || 'n/a';
  }
  return String(value);
}

function toNumberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function toConfidence(value: unknown): number | null {
  const candidate = toNumberOrNull(value);
  if (candidate === null) {
    return null;
  }
  return Math.min(1, Math.max(0, candidate));
}

function toEvidenceSummary(value: unknown): string {
  if (!value || typeof value !== 'object') {
    return 'n/a';
  }
  try {
    return JSON.stringify(value);
  } catch {
    return 'n/a';
  }
}

function hasLowConfidenceReason(category: string, state: string | null, confidence: number | null): string | null {
  const normalizedState = toStringValue(state).toLowerCase();
  if (normalizedState === 'uncertain' || normalizedState === 'unknown') {
    return `${category}:state:${normalizedState}`;
  }
  if (confidence !== null && confidence < LOW_CONFIDENCE_THRESHOLD) {
    return `${category}:confidence:${(confidence * 100).toFixed(0)}%`;
  }
  return null;
}

function toConfidenceDisplay(value: number | null): string {
  if (value === null) {
    return 'n/a';
  }
  return `${(value * 100).toFixed(0)}%`;
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return value as Record<string, unknown>;
}

function toReviewRow(segment: Record<string, unknown>): LowConfidenceReviewSegment | null {
  const segmentId = toStringValue(segment.segment_id);
  if (!segmentId || segmentId === 'n/a') {
    return null;
  }

  const confidenceByKey = toRecord(segment.confidence) ?? {};
  const tagStates = toRecord(segment.tag_states) ?? {};
  const tensionContribution = toRecord(segment.tension_contribution) ?? {};
  const dominanceContribution = toRecord(segment.dominance_contribution) ?? {};
  const summaryTag = toRecord(segment.summary_tag) ?? {};

  const typeState = toStringValue(tagStates.type);
  const speakerState = toStringValue(tagStates.speaker);
  const emotionState = toStringValue(tagStates.emotion);
  const tensionState = toStringValue(tensionContribution.state);
  const dominanceState = toStringValue(dominanceContribution.state);
  const summaryState = toStringValue(summaryTag.state);

  const typeConfidence = toConfidence(segment.type_confidence);
  const speakerConfidence = toConfidence(confidenceByKey.speaker);
  const emotionConfidence = toConfidence(confidenceByKey.emotion);
  const tensionConfidence = toConfidence(tensionContribution.confidence);
  const dominanceConfidence = toConfidence(dominanceContribution.confidence);
  const summaryConfidence = toConfidence(summaryTag.confidence);

  const reasons = [
    hasLowConfidenceReason('type', typeState, typeConfidence),
    hasLowConfidenceReason('speaker', speakerState, speakerConfidence),
    hasLowConfidenceReason('emotion', emotionState, emotionConfidence),
    hasLowConfidenceReason('tension', tensionState, tensionConfidence),
    hasLowConfidenceReason('dominance', dominanceState, dominanceConfidence),
    hasLowConfidenceReason('summary', summaryState, summaryConfidence),
  ]
    .filter((value): value is string => value !== null);

  const evidence = toEvidenceSummary({
    type: segment.type_evidence,
    speaker: segment.speaker_evidence,
    emotion: segment.emotion_evidence,
    tension: tensionContribution.evidence,
    dominance: dominanceContribution.evidence,
    summary: summaryTag.state,
  });

  return {
    segment_id: segmentId,
    chapter_id: toNumberOrNull(segment.chapter_id),
    original_text: toStringValue(segment.original_text),
    type_state: typeState,
    type_confidence: typeConfidence,
    speaker_state: speakerState,
    speaker_confidence: speakerConfidence,
    emotion_state: emotionState,
    emotion_confidence: emotionConfidence,
    tension_state: tensionState,
    tension_confidence: tensionConfidence,
    dominance_state: dominanceState,
    dominance_confidence: dominanceConfidence,
    summary_state: summaryState,
    summary_confidence: summaryConfidence,
    review_reasons: reasons,
    is_review_candidate: reasons.length > 0,
    evidence_summary: evidence,
  };
}

export function ProjectLowConfidenceReviewPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);

  const [reviewedSegments, setReviewedSegments] = useState<Set<string>>(new Set());
  const [reviewOnly, setReviewOnly] = useState(true);

  const reviewableSegments = useMemo<LowConfidenceReviewSegment[]>(() => {
    const rawSegments = exportPayloadQuery.data?.segments;
    if (!Array.isArray(rawSegments)) {
      return [];
    }
    return rawSegments
      .map((segment) => (typeof segment === 'object' && segment !== null ? toReviewRow(segment as Record<string, unknown>) : null))
      .filter((segment): segment is LowConfidenceReviewSegment => segment !== null);
  }, [exportPayloadQuery.data?.segments]);

  const reviewCandidates = useMemo(
    () => reviewableSegments.filter((segment) => segment.is_review_candidate),
    [reviewableSegments],
  );

  const visibleSegments = useMemo(
    () => (reviewOnly ? reviewCandidates : reviewableSegments),
    [reviewCandidates, reviewOnly, reviewableSegments],
  );

  const reviewedCount = useMemo(
    () => reviewableSegments.reduce((count, segment) => count + Number(reviewedSegments.has(segment.segment_id)), 0),
    [reviewableSegments, reviewedSegments],
  );

  function toggleReview(segmentId: string) {
    setReviewedSegments((prev) => {
      const next = new Set(prev);
      if (next.has(segmentId)) {
        next.delete(segmentId);
      } else {
        next.add(segmentId);
      }
      return next;
    });
  }

  function markAllReviewed() {
    setReviewedSegments(new Set(reviewableSegments.map((segment) => segment.segment_id)));
  }

  return (
    <WorkflowPageShell
      step="Step 05.3"
      title="Low-Confidence Region Review"
      description="Optional review queue for uncertain low-confidence tag regions across tagging categories."
      showOutputDisclaimer
      action={
        projectId !== null ? (
          <Button disabled={runId === null} onClick={() => navigate(projectRoute(projectId, 'export'))}>
            Continue to Export <ChevronRight className="size-4" />
          </Button>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-3">
            <span>Confidence Review Queue</span>
            <Button disabled={reviewableSegments.length === 0} onClick={markAllReviewed} size="sm" variant="outline">
              <ListChecks className="size-4" />
              Mark all reviewed
            </Button>
          </CardTitle>
          <CardDescription>Review uncertain low-confidence tags before export and downstream resolution.</CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="grid gap-2 text-sm text-muted-foreground lg:grid-cols-3">
            <p data-testid="low-confidence-review-total">
              Total segments: <strong className="text-foreground">{reviewableSegments.length}</strong>
            </p>
            <p data-testid="low-confidence-review-candidates">
              Review candidates: <strong className="text-foreground">{reviewCandidates.length}</strong>
            </p>
            <p data-testid="low-confidence-review-reviewed">
              Reviewed: <strong className="text-foreground">{reviewedCount}</strong>
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              data-testid="low-confidence-review-filter-btn"
              onClick={() => setReviewOnly(true)}
              size="sm"
              variant={reviewOnly ? 'default' : 'outline'}
            >
              <SearchX className="size-4" />
              Review candidates only
            </Button>
            <Button
              onClick={() => setReviewOnly(false)}
              size="sm"
              variant={reviewOnly ? 'outline' : 'default'}
            >
              <RefreshCcw className="size-4" />
              Show all segments
            </Button>
          </div>

          {exportPayloadQuery.isLoading ? <p>Loading export payload...</p> : null}
          {exportPayloadQuery.error ? <p className="text-destructive">{exportPayloadQuery.error.message}</p> : null}

          {!exportPayloadQuery.data ? (
            <p>Run export payload is required to review low-confidence regions.</p>
          ) : reviewableSegments.length === 0 ? (
            <p>No segments available yet.</p>
          ) : visibleSegments.length === 0 ? (
            <p>All review candidates are marked reviewed.</p>
          ) : (
            <div className="overflow-hidden rounded-xl border border-panel-border/70">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Segment</TableHead>
                    <TableHead>Signals</TableHead>
                    <TableHead>Reasons</TableHead>
                    <TableHead className="max-w-[14rem]">Evidence</TableHead>
                    <TableHead className="max-w-[20rem]">Text</TableHead>
                    <TableHead className="w-[8rem]">Review</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleSegments.map((segment) => {
                    const reviewed = reviewedSegments.has(segment.segment_id);
                    const highlight = segment.is_review_candidate && !reviewed;
                    return (
                      <TableRow
                        key={segment.segment_id}
                        className={[
                          highlight ? 'border-l-4 border-amber-400/80 bg-amber-500/5' : '',
                          reviewed ? 'opacity-65' : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                      >
                        <TableCell>
                          <div className="space-y-1 text-xs">
                            <p className="font-medium text-foreground">{segment.segment_id}</p>
                            <p className="text-muted-foreground">
                              {segment.chapter_id === null ? 'No chapter' : `Ch ${segment.chapter_id}`}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1 text-xs">
                            <p className="flex items-center gap-2">
                              <CircleDashed className="size-4" />
                              type: {segment.type_state} / {toConfidenceDisplay(segment.type_confidence)}
                            </p>
                            <p className="text-muted-foreground">
                              speaker: {segment.speaker_state} / {toConfidenceDisplay(segment.speaker_confidence)}
                            </p>
                            <p>emotion: {segment.emotion_state} / {toConfidenceDisplay(segment.emotion_confidence)}</p>
                            <p className="text-muted-foreground">
                              tension: {segment.tension_state} / {toConfidenceDisplay(segment.tension_confidence)}
                            </p>
                            <p>dominance: {segment.dominance_state} / {toConfidenceDisplay(segment.dominance_confidence)}</p>
                            <p className="text-muted-foreground">summary: {segment.summary_state} / {toConfidenceDisplay(segment.summary_confidence)}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1 text-xs">
                            {segment.review_reasons.length === 0 ? (
                              <p className="text-muted-foreground">n/a</p>
                            ) : (
                              segment.review_reasons.map((reason) => (
                                <p className="flex items-center gap-1 text-foreground" key={`${segment.segment_id}-${reason}`}>
                                  <ShieldAlert className="size-3" />
                                  {reason}
                                </p>
                              ))
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[14rem] text-xs text-muted-foreground">
                          {toStringValue(segment.evidence_summary) === 'n/a'
                            ? 'n/a'
                            : segment.evidence_summary.slice(0, 130)}
                        </TableCell>
                        <TableCell className="max-w-[20rem] text-xs text-foreground">{segment.original_text}</TableCell>
                        <TableCell>
                          <Button
                            data-testid={`low-confidence-review-toggle-${segment.segment_id}`}
                            onClick={() => toggleReview(segment.segment_id)}
                            size="sm"
                            variant={reviewed ? 'secondary' : 'default'}
                          >
                            {reviewed ? 'Reviewed' : 'Mark reviewed'}
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
