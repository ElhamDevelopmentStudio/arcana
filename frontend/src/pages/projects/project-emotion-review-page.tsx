import { useMemo, useState } from 'react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { ChevronRight, ListChecks, RefreshCw, SearchX, TrendingUp } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

type EmotionReviewSegment = {
  segment_id: string;
  chapter_id: number | null;
  original_text: string;
  emotion_valence: number | null;
  emotion_intensity: number | null;
  emotion_confidence: number | null;
  emotion_state: string;
  emotion_primary_label: string;
  emotion_secondary_label: string;
  emotion_shift: Record<string, unknown> | null;
  emotion_evidence: string;
  peak_or_trough: 'peak' | 'trough' | null;
  review_reasons: string[];
  is_review_candidate: boolean;
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

function toSignedPercent(value: number | null): string {
  if (value === null) {
    return 'n/a';
  }
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(0)}%`;
}

function toPercent(value: number | null): string {
  if (value === null) {
    return 'n/a';
  }
  return `${(value * 100).toFixed(0)}%`;
}

function hasEmotionShift(value: unknown): boolean {
  return Boolean(
    value &&
      typeof value === 'object' &&
      'has_shift' in value &&
      typeof (value as Record<string, unknown>).has_shift === 'boolean' &&
      (value as Record<string, unknown>).has_shift,
  );
}

function buildReviewCandidates(
  rawSegments: EmotionReviewSegment[],
): EmotionReviewSegment[] {
  return rawSegments.map((segment, index, segments) => {
    const prevValence = index > 0 ? segments[index - 1].emotion_valence : null;
    const nextValence = index + 1 < segments.length ? segments[index + 1].emotion_valence : null;
    const currentValence = segment.emotion_valence;

    let peakOrTrough: EmotionReviewSegment['peak_or_trough'] = null;
    if (currentValence !== null && prevValence !== null && nextValence !== null) {
      if (currentValence > prevValence && currentValence > nextValence) {
        peakOrTrough = 'peak';
      } else if (currentValence < prevValence && currentValence < nextValence) {
        peakOrTrough = 'trough';
      }
    }

    const reasons: string[] = [];
    const state = segment.emotion_state.toLowerCase();
    const lowConfidence = (segment.emotion_confidence ?? 0) < LOW_CONFIDENCE_THRESHOLD;
    const confidenceReview = state === 'uncertain' || state === 'unknown' || lowConfidence;

    if (confidenceReview) {
      reasons.push('confidence');
    }
    if (peakOrTrough !== null) {
      reasons.push(peakOrTrough);
    }
    if (hasEmotionShift(segment.emotion_shift)) {
      reasons.push('shift');
    }

    return {
      ...segment,
      peak_or_trough: peakOrTrough,
      review_reasons: reasons,
      is_review_candidate: reasons.length > 0,
    };
  });
}

function toReviewRow(segment: Record<string, unknown>): EmotionReviewSegment | null {
  const emotionValence = toNumberOrNull(segment.emotion_valence);
  const emotionIntensity = toNumberOrNull(segment.emotion_intensity);
  const emotionConfidence = toConfidence(segment.emotion_confidence);
  const segmentId = toStringValue(segment.segment_id);

  if (!segmentId || segmentId === 'n/a') {
    return null;
  }

  return {
    segment_id: segmentId,
    chapter_id: toNumberOrNull(segment.chapter_id),
    original_text: toStringValue(segment.original_text),
    emotion_valence: emotionValence,
    emotion_intensity: emotionIntensity,
    emotion_confidence: emotionConfidence,
    emotion_state: toStringValue(segment.emotion_state).toLowerCase(),
    emotion_primary_label: toStringValue(segment.emotion_primary_label),
    emotion_secondary_label: toStringValue(segment.emotion_secondary_label),
    emotion_shift: segment.emotion_shift as Record<string, unknown> | null,
    emotion_evidence: toEvidenceSummary(segment.emotion_evidence),
    peak_or_trough: null,
    review_reasons: [],
    is_review_candidate: false,
  };
}

export function ProjectEmotionReviewPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);

  const [reviewedSegments, setReviewedSegments] = useState<Set<string>>(new Set());
  const [reviewOnly, setReviewOnly] = useState(true);

  const reviewableSegments = useMemo<EmotionReviewSegment[]>(() => {
    const rawSegments = exportPayloadQuery.data?.segments;
    if (!Array.isArray(rawSegments)) {
      return [];
    }

    const parsedSegments = rawSegments
      .map((segment) => (typeof segment === 'object' && segment !== null ? toReviewRow(segment as Record<string, unknown>) : null))
      .filter((row): row is EmotionReviewSegment => row !== null);

    return buildReviewCandidates(parsedSegments);
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
      step="Step 05.2"
      title="Emotion Peak/Trough Review"
      description="Optional review of emotional peaks, troughs, and low-confidence emotion tags."
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
            <span>Emotional Signal Queue</span>
            <Button disabled={reviewableSegments.length === 0} onClick={markAllReviewed} size="sm" variant="outline">
              <ListChecks className="size-4" />
              Mark all reviewed
            </Button>
          </CardTitle>
          <CardDescription>
            Review high-variance emotion segments and uncertain emotion signals before moving to export.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="grid gap-2 text-sm text-muted-foreground lg:grid-cols-3">
            <p data-testid="emotion-review-total">
              Total segments: <strong className="text-foreground">{reviewableSegments.length}</strong>
            </p>
            <p data-testid="emotion-review-candidates">
              Review candidates: <strong className="text-foreground">{reviewCandidates.length}</strong>
            </p>
            <p data-testid="emotion-review-reviewed">
              Reviewed: <strong className="text-foreground">{reviewedCount}</strong>
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              data-testid="emotion-review-filter-btn"
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
              <RefreshCw className="size-4" />
              Show all segments
            </Button>
          </div>

          {exportPayloadQuery.isLoading ? <p>Loading export payload...</p> : null}
          {exportPayloadQuery.error ? <p className="text-destructive">{exportPayloadQuery.error.message}</p> : null}

          {!exportPayloadQuery.data ? (
            <p>Run export payload is required to review emotional signals.</p>
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
                    <TableHead>Valence</TableHead>
                    <TableHead>Intensity</TableHead>
                    <TableHead>Emotion</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead className="max-w-[16rem]">Evidence</TableHead>
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
                            <p>{toSignedPercent(segment.emotion_valence)}</p>
                            <p className="text-muted-foreground">
                              {segment.peak_or_trough === 'peak'
                                ? 'Peak'
                                : segment.peak_or_trough === 'trough'
                                  ? 'Trough'
                                  : 'stable'}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>{toPercent(segment.emotion_intensity)}</TableCell>
                        <TableCell>
                          <div className="space-y-1 text-xs">
                            <p className="font-medium text-foreground">{segment.emotion_primary_label}</p>
                            <p className="text-muted-foreground">{segment.emotion_secondary_label}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={segment.emotion_state === 'certain' ? 'default' : 'secondary'}>
                            {segment.emotion_state}
                          </Badge>
                        </TableCell>
                        <TableCell>{toPercent(segment.emotion_confidence)}</TableCell>
                        <TableCell className="text-xs">
                          <div className="space-y-1">
                            {segment.review_reasons.length === 0 ? (
                              <p className="text-muted-foreground">n/a</p>
                            ) : (
                              segment.review_reasons.map((reason) => (
                                <p className="flex items-center gap-1 text-foreground" key={`${segment.segment_id}-${reason}`}>
                                  <TrendingUp className="size-3" />
                                  {reason}
                                </p>
                              ))
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[16rem] text-xs text-muted-foreground">
                          {toStringValue(segment.emotion_evidence) === 'n/a'
                            ? 'n/a'
                            : segment.emotion_evidence.slice(0, 120)}
                        </TableCell>
                        <TableCell className="max-w-[20rem] text-xs text-foreground">{segment.original_text}</TableCell>
                        <TableCell>
                          <Button
                            data-testid={`emotion-review-toggle-${segment.segment_id}`}
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
