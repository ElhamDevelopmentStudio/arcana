import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';
import { Download } from 'lucide-react';

type MajorTagConfidenceRow = {
  segment_id: string;
  chapter_id: number | null;
  speaker_confidence: number | null;
  emotion_confidence: number | null;
  type_confidence: number | null;
  tension_confidence: number | null;
  dominance_confidence: number | null;
  summary_confidence: number | null;
};

function toNumberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function toRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function toConfidence(value: unknown): number | null {
  const candidate = toNumberOrNull(value);
  if (candidate === null) {
    return null;
  }
  return Math.min(1, Math.max(0, candidate));
}

function toPercent(value: number | null): string {
  if (value === null) {
    return 'n/a';
  }
  return `${Math.round(value * 100)}%`;
}

function toMajorTagConfidenceRow(segment: Record<string, unknown>): MajorTagConfidenceRow {
  const segmentId = typeof segment.segment_id === 'string' ? segment.segment_id : String(segment.segment_id ?? 'n/a');
  const confidence = toRecord(segment.confidence);
  const tensionContribution = toRecord(segment.tension_contribution);
  const dominanceContribution = toRecord(segment.dominance_contribution);
  const summaryTag = toRecord(segment.summary_tag);

  return {
    segment_id: segmentId,
    chapter_id: toNumberOrNull(segment.chapter_id),
    speaker_confidence: toConfidence(confidence.speaker),
    emotion_confidence: toConfidence(confidence.emotion),
    type_confidence: toConfidence(confidence.type),
    tension_confidence:
      toConfidence(toRecord(tensionContribution.confidence).value) ?? toConfidence(tensionContribution.confidence) ?? toConfidence(confidence.tension),
    dominance_confidence:
      toConfidence(toRecord(dominanceContribution.confidence).value) ??
      toConfidence(dominanceContribution.confidence) ??
      toConfidence(confidence.dominance),
    summary_confidence: toConfidence(summaryTag.confidence) ?? toConfidence(confidence.summary),
  };
}

export function ProjectExportPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);
  const majorTagConfidenceRows = exportPayloadQuery.data?.segments
    ?.map((segment) => {
      if (!segment || typeof segment !== 'object') {
        return null;
      }
      return toMajorTagConfidenceRow(segment as Record<string, unknown>);
    })
    .filter((row): row is MajorTagConfidenceRow => row !== null && row.segment_id !== 'n/a')
    .slice(0, 10) ?? [];

  function downloadExportJson() {
    if (!exportPayloadQuery.data || projectId === null || runId === null) {
      return;
    }
    const blob = new Blob([JSON.stringify(exportPayloadQuery.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `project-${projectId}-run-${runId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <WorkflowPageShell
      step="Step 06"
      title="Exports"
      description="Review export readiness and download generated outputs. This page is dedicated to export artifacts only."
      showOutputDisclaimer
      action={
        projectId !== null ? (
          <Button onClick={() => navigate(projectRoute(projectId, 'dashboards'))}>Continue to Dashboards</Button>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Export Package</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>Project: {projectId ?? 'n/a'}</p>
          <p>Run: {runId ?? 'n/a'}</p>
          <p>{exportPayloadQuery.data ? 'Export payload is ready for download.' : 'Awaiting run/export data.'}</p>

          <Button disabled={!exportPayloadQuery.data} onClick={downloadExportJson}>
            <Download className="size-4" />
            Download JSON
          </Button>

          {exportPayloadQuery.isLoading ? <p>Loading export payload...</p> : null}
          {exportPayloadQuery.error ? <p className="text-destructive">{exportPayloadQuery.error.message}</p> : null}
          {exportPayloadQuery.data ? (
            <>
              <Card className="border-dashed">
                <CardHeader>
                  <CardTitle>Major tag confidence sample</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-muted-foreground">
                  <p>Preview the first 10 tag-bearing segments to inspect confidence spread before export.</p>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Segment</TableHead>
                        <TableHead>Speaker</TableHead>
                        <TableHead>Emotion</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Tension</TableHead>
                        <TableHead>Dominance</TableHead>
                        <TableHead>Summary</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {majorTagConfidenceRows.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-muted-foreground">
                            No major tag confidence fields were detected in this export payload.
                          </TableCell>
                        </TableRow>
                      ) : (
                        majorTagConfidenceRows.map((segment) => (
                          <TableRow key={segment.segment_id} data-testid={`export-confidence-row-${segment.segment_id}`}>
                            <TableCell>
                              <p>
                                Ch {segment.chapter_id ?? 'n/a'} / {segment.segment_id}
                              </p>
                            </TableCell>
                            <TableCell>{toPercent(segment.speaker_confidence)}</TableCell>
                            <TableCell>{toPercent(segment.emotion_confidence)}</TableCell>
                            <TableCell>{toPercent(segment.type_confidence)}</TableCell>
                            <TableCell>{toPercent(segment.tension_confidence)}</TableCell>
                            <TableCell>{toPercent(segment.dominance_confidence)}</TableCell>
                            <TableCell>{toPercent(segment.summary_confidence)}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              <pre className="max-h-72 overflow-auto rounded-xl bg-muted/35 p-3 text-xs">
                {JSON.stringify(exportPayloadQuery.data, null, 2)}
              </pre>
            </>
          ) : (
            <p>JSON/CSV/chunked export links and manifest metadata with deterministic run context.</p>
          )}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
