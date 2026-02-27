import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  useCreateComparisonWorkspaceMutation,
  useExportCsvMutation,
  useExportPayloadQuery,
  useRunDetailQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { useNavigate, useParams } from 'react-router-dom';
import { Download } from 'lucide-react';
import { type ChangeEvent, useMemo, useState } from 'react';

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

function toAllowedExportFormats(config: Record<string, unknown> | undefined): Set<string> | null {
  const rawFormats = config?.export_formats;
  if (!Array.isArray(rawFormats)) {
    return null;
  }
  const normalized = rawFormats
    .filter((value): value is string => typeof value === 'string')
    .map((value) => value.trim().toLowerCase())
    .filter((value) => value.length > 0);
  return new Set(normalized);
}

export function ProjectExportPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);
  const exportCsvMutation = useExportCsvMutation(projectId, runId);
  const createComparisonWorkspaceMutation = useCreateComparisonWorkspaceMutation();
  const runDetailQuery = useRunDetailQuery(projectId, runId);
  const [minimumConfidence, setMinimumConfidence] = useState(0.8);
  const [showBelowThreshold, setShowBelowThreshold] = useState(true);
  const [comparisonWorkspaceName, setComparisonWorkspaceName] = useState('');
  const [createdComparisonWorkspaceId, setCreatedComparisonWorkspaceId] = useState<number | null>(null);

  const allowedExportFormats = useMemo(
    () => toAllowedExportFormats(runDetailQuery.data?.config as Record<string, unknown> | undefined),
    [runDetailQuery.data?.config],
  );
  const runStatus = runDetailQuery.data?.status ?? null;
  const isRunCompleted = runStatus === 'completed';
  const isJsonAllowedByFormat = allowedExportFormats === null || allowedExportFormats.has('json');
  const isCsvAllowedByFormat = allowedExportFormats === null || allowedExportFormats.has('csv');
  const isJsonExportEnabled = Boolean(exportPayloadQuery.data) && isRunCompleted && isJsonAllowedByFormat;
  const isCsvExportEnabled = Boolean(exportPayloadQuery.data) && isRunCompleted && isCsvAllowedByFormat;

  const majorTagConfidenceRows = exportPayloadQuery.data?.segments
    ?.map((segment) => {
      if (!segment || typeof segment !== 'object') {
        return null;
      }
      return toMajorTagConfidenceRow(segment as Record<string, unknown>);
    })
    .filter((row): row is MajorTagConfidenceRow => row !== null && row.segment_id !== 'n/a') ?? [];

  const confidenceFilteredRows = useMemo(
    () =>
      majorTagConfidenceRows
        .filter((segment) => {
          const allConfidences = [
            segment.speaker_confidence,
            segment.emotion_confidence,
            segment.type_confidence,
            segment.tension_confidence,
            segment.dominance_confidence,
            segment.summary_confidence,
          ].filter((value): value is number => typeof value === 'number');

          if (allConfidences.length === 0) {
            return false;
          }

          const minConfidence = allConfidences.reduce((minimum, current) => (current < minimum ? current : minimum), 1);
          const threshold = Math.min(1, Math.max(0, minimumConfidence));

          return showBelowThreshold ? minConfidence < threshold : minConfidence >= threshold;
        })
        .slice(0, 10),
    [majorTagConfidenceRows, minimumConfidence, showBelowThreshold],
  );

  function updateMinimumConfidence(event: ChangeEvent<HTMLInputElement>) {
    setMinimumConfidence(Math.round(Number(event.target.value) * 100) / 100);
  }

  function toggleFilterScope() {
    setShowBelowThreshold((prev) => !prev);
  }

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

  async function downloadExportCsv() {
    if (projectId === null || runId === null) {
      return;
    }
    try {
      const csvPayload = await exportCsvMutation.trigger();
      const blob = new Blob([csvPayload], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `project-${projectId}-run-${runId}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      // surfaced via exportCsvMutation.error
    }
  }

  async function createComparisonWorkspace() {
    const trimmedName = comparisonWorkspaceName.trim();
    if (!trimmedName) {
      return;
    }
    try {
      const createdWorkspace = await createComparisonWorkspaceMutation.trigger({ name: trimmedName });
      setCreatedComparisonWorkspaceId(createdWorkspace.workspace_id);
    } catch {
      // surfaced via createComparisonWorkspaceMutation.error
    }
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
          {runDetailQuery.isLoading ? <p>Loading export availability...</p> : null}
          {runStatus !== null && runStatus !== 'completed' ? (
            <p className="text-muted-foreground">Exports are unavailable while run status is {runStatus}.</p>
          ) : null}
          {isRunCompleted && !isJsonAllowedByFormat ? (
            <p className="text-muted-foreground">JSON export is disabled for this run configuration.</p>
          ) : null}
          {isRunCompleted && !isCsvAllowedByFormat ? (
            <p className="text-muted-foreground">CSV export is disabled for this run configuration.</p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button disabled={!isJsonExportEnabled} onClick={downloadExportJson}>
              <Download className="size-4" />
              Download JSON
            </Button>
            <Button
              disabled={!isCsvExportEnabled || exportCsvMutation.isMutating}
              onClick={downloadExportCsv}
              variant="outline"
            >
              <Download className="size-4" />
              {exportCsvMutation.isMutating ? 'Downloading CSV...' : 'Download CSV'}
            </Button>
          </div>

          {exportPayloadQuery.isLoading ? <p>Loading export payload...</p> : null}
          {exportPayloadQuery.error ? <p className="text-destructive">{exportPayloadQuery.error.message}</p> : null}
          {runDetailQuery.error ? <p className="text-destructive">{runDetailQuery.error.message}</p> : null}
          {exportCsvMutation.error ? <p className="text-destructive">{exportCsvMutation.error.message}</p> : null}
          {exportPayloadQuery.data ? (
            <>
              <Card className="border-dashed">
                <CardHeader>
                  <CardTitle>Major tag confidence sample</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-muted-foreground">
                  <p>Preview the first 10 tag-bearing segments to inspect confidence spread before export.</p>
                  <div className="space-y-2 rounded-xl border border-panel-border/50 bg-muted/30 px-3 py-2">
                    <p className="text-xs font-medium text-foreground">
                      Showing {confidenceFilteredRows.length} rows where min confidence is{' '}
                      {showBelowThreshold ? 'below' : 'at least'} {Math.round(minimumConfidence * 100)}%
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="text-xs" htmlFor="export-confidence-threshold">
                        Threshold:
                        <span className="ml-1.5 text-foreground">{Math.round(minimumConfidence * 100)}%</span>
                      </label>
                      <input
                        id="export-confidence-threshold"
                        aria-label="Confidence threshold"
                        data-testid="export-confidence-threshold"
                        min={0}
                        max={1}
                        onChange={updateMinimumConfidence}
                        step={0.01}
                        type="range"
                        value={minimumConfidence}
                      />
                      <Button onClick={toggleFilterScope} size="sm" type="button" variant="outline">
                        {showBelowThreshold ? 'Show at or above threshold' : 'Show below threshold'}
                      </Button>
                    </div>
                  </div>
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
                      {confidenceFilteredRows.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-muted-foreground">
                            No major tag confidence fields were detected for current threshold.
                          </TableCell>
                        </TableRow>
                      ) : (
                        confidenceFilteredRows.map((segment) => (
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

      <Card>
        <CardHeader>
          <CardTitle>Comparison Workspace</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>Create a comparison workspace to group multiple runs for aligned-curve analysis.</p>
          <div className="flex max-w-xl flex-col gap-2 sm:flex-row sm:items-center">
            <input
              aria-label="Comparison workspace name"
              className="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm"
              data-testid="comparison-workspace-name-input"
              onChange={(event) => setComparisonWorkspaceName(event.target.value)}
              placeholder="Enter workspace name"
              value={comparisonWorkspaceName}
            />
            <Button
              data-testid="comparison-workspace-create-button"
              disabled={comparisonWorkspaceName.trim().length === 0 || createComparisonWorkspaceMutation.isMutating}
              onClick={createComparisonWorkspace}
              type="button"
              variant="outline"
            >
              {createComparisonWorkspaceMutation.isMutating ? 'Creating workspace...' : 'Create comparison workspace'}
            </Button>
          </div>
          {createComparisonWorkspaceMutation.error ? (
            <p className="text-destructive">{createComparisonWorkspaceMutation.error.message}</p>
          ) : null}
          {createdComparisonWorkspaceId !== null ? (
            <div className="space-y-2">
              <p data-testid="comparison-workspace-created-id">
                Workspace created: <strong className="text-foreground">#{createdComparisonWorkspaceId}</strong>
              </p>
              <Button
                data-testid="comparison-workspace-open-button"
                onClick={() => navigate(`/comparison-workspaces/${createdComparisonWorkspaceId}`)}
                size="sm"
                type="button"
                variant="outline"
              >
                Open comparison workspace
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
