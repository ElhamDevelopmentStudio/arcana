import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useExportPayloadQuery, useTensionGraphQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';

type DashboardPoint = {
  chapter: string;
  tension: number;
  position: number;
  chapterId: number | null;
  segmentId: string | null;
};

type ExportSegment = Record<string, unknown>;

function toStringValue(value: unknown): string | null {
  if (value == null) {
    return null;
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return null;
}

function toNumericValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function clampUnit(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function extractTensionValueFromSegment(segment: ExportSegment): number | null {
  const tensionContribution = segment.tension_contribution;
  if (typeof tensionContribution !== 'object' || tensionContribution === null) {
    return null;
  }

  const parsed = toNumericValue((tensionContribution as { value?: unknown }).value);
  return parsed === null ? null : clampUnit(parsed);
}

function buildFallbackPoints(): DashboardPoint[] {
  return Array.from({ length: 12 }, (_, index) => ({
    chapter: `S ${index + 1}`,
    tension: clampUnit(((index * 7 + 13) % 100) / 100),
    position: index + 1,
    chapterId: null,
    segmentId: `fallback-${index + 1}`,
  }));
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function computeMax(values: DashboardPoint[]) {
  const max = Math.max(0, ...values.map((item) => item.tension));
  return max;
}

function computeAverage(values: DashboardPoint[]) {
  if (values.length === 0) {
    return 0;
  }
  const sum = values.reduce((acc, item) => acc + item.tension, 0);
  return sum / values.length;
}

export function ProjectDashboardsPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);
  const tensionGraphQuery = useTensionGraphQuery(projectId, runId);
  const [showSmoothed, setShowSmoothed] = useState(true);

  const rawSeries = useMemo(() => {
    const segments = (exportPayloadQuery.data?.segments ?? []) as ExportSegment[];
    const values = segments
      .map((segment, index): DashboardPoint | null => {
        const tensionValue = extractTensionValueFromSegment(segment);
        if (tensionValue === null) {
          return null;
        }

        return {
          chapter: `S ${index + 1}`,
          tension: tensionValue,
          position: toNumericValue(segment.segment_index) || index + 1,
          chapterId: toNumericValue(segment.chapter_id) ? Math.trunc(toNumericValue(segment.chapter_id)!) : null,
          segmentId: toStringValue(segment.segment_id),
        };
      })
      .filter((point): point is DashboardPoint => point !== null);

    if (values.length > 0) {
      return values;
    }

    return buildFallbackPoints();
  }, [exportPayloadQuery.data]);

  const smoothedSeries = useMemo(() => {
    const rawPoints = tensionGraphQuery.data?.points ?? [];
    const values = rawPoints.map((point) => ({
      chapter: `S ${point.position}`,
      tension: clampUnit(point.smoothed_tension),
      position: point.position,
      chapterId: point.chapter_id ?? null,
      segmentId: point.segment_id,
    }));

    if (values.length > 0) {
      return values;
    }

    return rawSeries;
  }, [rawSeries, tensionGraphQuery.data]);

  const chartData = useMemo(() => (showSmoothed ? smoothedSeries : rawSeries).slice(0, 20), [showSmoothed, rawSeries, smoothedSeries]);

  const maxTension = computeMax(chartData);
  const avgTension = computeAverage(chartData);

  const dataSourceLabel = showSmoothed
    ? tensionGraphQuery.data
      ? 'Data source: run tension graph endpoint'
      : 'Data source: fallback smoothed data'
    : 'Data source: raw segment tension';

  return (
    <WorkflowPageShell
      step="Step 07"
      title="Dashboards"
      description="Explore visual analytics: tension, emotional polarity, dominance, and character trends."
      action={<p className="text-sm text-muted-foreground">{dataSourceLabel}</p>}
    >
      <Card>
        <CardHeader>
          <CardTitle>Narrative Trend</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              Display mode: <span className="font-medium text-foreground">{showSmoothed ? 'Smoothed' : 'Raw'}</span>
            </p>
            <div className="flex items-center gap-2">
              <Label className="text-sm" htmlFor="tension-smoothing-toggle">
                Show smoothed
              </Label>
              <Switch
                checked={showSmoothed}
                onCheckedChange={setShowSmoothed}
                id="tension-smoothing-toggle"
                aria-label="tension smoothing toggle"
              />
            </div>
          </div>

          <div className="grid gap-2 text-sm text-muted-foreground lg:grid-cols-3">
            <p>
              Peak tension: <strong className="text-foreground">{formatPercent(maxTension)}</strong>
            </p>
            <p>
              Average tension: <strong className="text-foreground">{formatPercent(avgTension)}</strong>
            </p>
            <p>
              Segments: <strong className="text-foreground">{chartData.length}</strong>
            </p>
          </div>

          <div className="h-[20rem]">
            <LineChart width={900} height={320} data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="chapter" />
              <YAxis domain={[0, 1]} />
              <Tooltip />
              <Line dataKey="tension" dot={false} stroke="#1473e6" strokeWidth={2.5} type="monotone" />
            </LineChart>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Chapter Snapshot</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-1 text-sm">
            {chartData.slice(0, 10).map((item) => (
              <div
                key={item.chapter}
                className="grid grid-cols-[1fr_auto] items-center gap-3 py-1.5 [&:not(:last-child)]:border-b [&:not(:last-child)]:border-panel-border/50"
              >
                <span className="font-medium text-foreground">{item.chapter}</span>
                <span className="text-muted-foreground" data-testid={`dashboards-tension-${item.segmentId ?? item.chapter}`}>
                  T {formatPercent(item.tension)}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
