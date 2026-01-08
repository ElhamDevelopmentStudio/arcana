import { useMemo, useState } from 'react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { ChevronRight, ListChecks, RefreshCcw, SearchX } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

type SpeakerReviewSegment = {
  segment_id: string;
  chapter_id: number | null;
  original_text: string;
  speaker: string;
  speaker_id: number | null;
  speaker_state: string;
  speaker_confidence: number | null;
  is_review_candidate: boolean;
  speaker_evidence: string;
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

function toReviewRow(segment: Record<string, unknown>): SpeakerReviewSegment {
  const confidenceValue =
    typeof segment.confidence === 'object' && segment.confidence !== null
      ? (segment.confidence as Record<string, unknown>).speaker
      : null;
  const speakerConfidence = toConfidence(confidenceValue);
  const speaker = toStringValue(segment.speaker);
  const reviewState = toStringValue(segment.speaker_state).toLowerCase();
  const isUnknownSpeaker = !speaker || speaker.toLowerCase() === 'unknown';
  const confidenceForRule = speakerConfidence ?? 0;

  return {
    segment_id: toStringValue(segment.segment_id),
    chapter_id: toNumberOrNull(segment.chapter_id),
    original_text: toStringValue(segment.original_text),
    speaker,
    speaker_id: toNumberOrNull(segment.speaker_id),
    speaker_state: reviewState || 'uncertain',
    speaker_confidence: speakerConfidence,
    is_review_candidate: isUnknownSpeaker || reviewState === 'uncertain' || confidenceForRule < LOW_CONFIDENCE_THRESHOLD,
    speaker_evidence: toEvidenceSummary(segment.speaker_evidence),
  };
}

function shortText(text: string): string {
  return text.length > 140 ? `${text.slice(0, 137)}…` : text;
}

function formatConfidence(value: number | null): string {
  if (value === null) {
    return 'n/a';
  }
  return `${(value * 100).toFixed(0)}%`;
}

export function ProjectSpeakerReviewPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);

  const [reviewedSegments, setReviewedSegments] = useState<Set<string>>(new Set());
  const [reviewOnly, setReviewOnly] = useState(true);

  const segments = useMemo<SpeakerReviewSegment[]>(() => {
    const rawSegments = exportPayloadQuery.data?.segments;
    if (!Array.isArray(rawSegments)) {
      return [];
    }
    return rawSegments
      .map((segment) => (typeof segment === 'object' && segment !== null ? toReviewRow(segment as Record<string, unknown>) : null))
      .filter((row): row is SpeakerReviewSegment => row !== null && Boolean(row.segment_id));
  }, [exportPayloadQuery.data?.segments]);

  const reviewCandidates = useMemo(
    () => segments.filter((segment) => segment.is_review_candidate),
    [segments],
  );

  const visibleSegments = useMemo(
    () => (reviewOnly ? reviewCandidates : segments),
    [reviewCandidates, reviewOnly, segments],
  );

  const reviewedCount = useMemo(
    () => segments.reduce((count, segment) => count + Number(reviewedSegments.has(segment.segment_id)), 0),
    [segments, reviewedSegments],
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
    setReviewedSegments(new Set(segments.map((segment) => segment.segment_id)));
  }

  return (
    <WorkflowPageShell
      step="Step 05.1"
      title="Speaker Tag Review"
      description="Optional review of low-confidence speaker tags extracted by the pipeline."
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
            <span>Speaker Attribution Queue</span>
            <Button disabled={segments.length === 0} onClick={markAllReviewed} size="sm" variant="outline">
              <ListChecks className="size-4" />
              Mark all reviewed
            </Button>
          </CardTitle>
          <CardDescription>
            Review only low-confidence entries by default, then continue to export.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="grid gap-2 text-sm text-muted-foreground lg:grid-cols-3">
            <p data-testid="speaker-review-total">
              Total segments: <strong className="text-foreground">{segments.length}</strong>
            </p>
            <p data-testid="speaker-review-candidates">
              Review candidates: <strong className="text-foreground">{reviewCandidates.length}</strong>
            </p>
            <p data-testid="reviewed-count">
              Reviewed: <strong className="text-foreground">{reviewedCount}</strong>
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              data-testid="speaker-review-filter-btn"
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
            <p>Run export payload is required to review speaker tags.</p>
          ) : segments.length === 0 ? (
            <p>No segments available yet.</p>
          ) : visibleSegments.length === 0 ? (
            <p>All review candidates are marked reviewed.</p>
          ) : (
            <div className="overflow-hidden rounded-xl border border-panel-border/70">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Segment</TableHead>
                    <TableHead>Speaker</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Evidence</TableHead>
                    <TableHead>Text</TableHead>
                    <TableHead className="w-[7rem]">Review</TableHead>
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
                            <p className="text-muted-foreground">{segment.chapter_id === null ? 'No chapter' : `Ch ${segment.chapter_id}`}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1 text-xs">
                            <p className="font-medium text-foreground">{segment.speaker}</p>
                            <p className="text-muted-foreground">id: {segment.speaker_id ?? 'n/a'}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={segment.speaker_state === 'certain' ? 'default' : 'secondary'}>
                            {segment.speaker_state}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatConfidence(segment.speaker_confidence)}</TableCell>
                        <TableCell className="max-w-[16rem] text-xs text-muted-foreground">
                          {shortText(segment.speaker_evidence)}
                        </TableCell>
                        <TableCell className="max-w-[20rem] text-xs text-foreground">
                          {shortText(segment.original_text)}
                        </TableCell>
                        <TableCell>
                          <Button
                            data-testid={`speaker-review-toggle-${segment.segment_id}`}
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
