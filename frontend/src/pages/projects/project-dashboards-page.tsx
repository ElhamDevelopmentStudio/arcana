import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useCharacterAnalyticsQuery, useExportPayloadQuery, useTensionGraphQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import type { CharacterAnalyticsResponseDto, TensionGraphPeakMarkerDto, TensionGraphPlateauRegionDto } from '@/app/schemas/api';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, Legend, ReferenceArea, Tooltip, XAxis, YAxis } from 'recharts';

type DashboardPoint = {
  chapter: string;
  tension: number;
  position: number;
  chapterId: number | null;
  segmentId: string | null;
};

type PeakMarkerPoint = {
  position: number;
  tension: number;
  segmentId: string | null;
  peakType: string;
  severity: string;
};

type PlateauOverlay = {
  regionType: string;
  startPosition: number;
  endPosition: number;
  yMin: number;
  yMax: number;
  average: number;
  key: string;
};

type ExportSegment = Record<string, unknown>;
type CharacterTrendSeriesPoint = {
  chapterLabel: string;
  chapterIndex: number;
  [characterName: string]: string | number;
};

type CharacterProminenceRow = {
  name: string;
  mentionsPer1000Words: number;
  totalMentions: number;
  firstAppearanceChapter: number | null;
  lastAppearanceChapter: number | null;
  dialogueLineCount: number;
};

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

function buildCharacterTotalsByName(analytics: CharacterAnalyticsResponseDto | null): Map<string, number> {
  const totals = new Map<string, number>();
  for (const record of analytics?.character_mentions_by_chapter ?? []) {
    for (const [name, count] of Object.entries(record.mention_counts)) {
      const previous = totals.get(name) ?? 0;
      totals.set(name, previous + count);
    }
  }

  for (const name of Object.keys(analytics?.character_first_appearance_chapter_index ?? {})) {
    totals.set(name, totals.get(name) ?? 0);
  }

  return totals;
}

function buildCharacterProminenceRows(analytics: CharacterAnalyticsResponseDto | null): CharacterProminenceRow[] {
  const totals = buildCharacterTotalsByName(analytics);

  const rows = Array.from(totals.entries()).map(([name, totalMentions]) => ({
    name,
    mentionsPer1000Words: analytics?.character_mentions_per_1000_words[name] ?? 0,
    totalMentions,
    firstAppearanceChapter: analytics?.character_first_appearance_chapter_index[name] ?? null,
    lastAppearanceChapter: analytics?.character_last_appearance_chapter_index[name] ?? null,
    dialogueLineCount: analytics?.character_dialogue_line_counts[name] ?? 0,
  }));

  rows.sort((left, right) => {
    if (right.mentionsPer1000Words !== left.mentionsPer1000Words) {
      return right.mentionsPer1000Words - left.mentionsPer1000Words;
    }
    return right.totalMentions - left.totalMentions;
  });
  return rows;
}

function buildCharacterTrendSeries(
  analytics: CharacterAnalyticsResponseDto | null,
  trendCharacters: string[],
): CharacterTrendSeriesPoint[] {
  if (!analytics) {
    return [];
  }

  const sortedChapters = [...analytics.character_mentions_by_chapter].sort(
    (left, right) => left.chapter_index - right.chapter_index,
  );

  return sortedChapters.map((record) => {
    const point: CharacterTrendSeriesPoint = {
      chapterLabel: `Ch ${record.chapter_index}`,
      chapterIndex: record.chapter_index,
    };
    for (const name of trendCharacters) {
      point[name] = record.mention_counts[name] ?? 0;
    }
    return point;
  });
}

const CHARACTER_TREND_PALETTE = ['#0ea5e9', '#8b5cf6', '#f97316', '#22c55e', '#ec4899'];

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

function normalizePeakMarkers(
  peaks: TensionGraphPeakMarkerDto[] | undefined,
): PeakMarkerPoint[] {
  return (peaks ?? [])
    .map((peak) => {
      if (peak.position === null || peak.position === undefined || Number.isNaN(peak.position)) {
        return null;
      }
      return {
        position: peak.position,
        tension: clampUnit(peak.tension_value),
        segmentId: peak.segment_id ?? null,
        peakType: peak.peak_type,
        severity: peak.severity,
      };
    })
    .filter((item): item is PeakMarkerPoint => item !== null);
}

function normalizePlateauOverlays(
  regions: TensionGraphPlateauRegionDto[] | undefined,
): PlateauOverlay[] {
  return (regions ?? [])
    .map((region) => {
      const segmentIndices = region.segment_indices ?? [];
      const start = region.start_position ?? segmentIndices[0] ?? null;
      const end = region.end_position ?? segmentIndices[segmentIndices.length - 1] ?? null;

      if (start === null || end === null || Number.isNaN(start) || Number.isNaN(end)) {
        return null;
      }

      return {
        regionType: region.region_type,
        startPosition: Math.min(start, end),
        endPosition: Math.max(start, end),
        yMin: clampUnit(region.tension_value_range.min),
        yMax: clampUnit(region.tension_value_range.max),
        average: clampUnit(region.average_tension),
        key: `plateau-${region.region_type}-${start}-${end}`,
      };
    })
    .filter((item): item is PlateauOverlay => item !== null);
}

function PeakMarkerPointShape({
  cx,
  cy,
  payload,
}: {
  cx?: number;
  cy?: number;
  payload?: {
    peakMarkerSeverity?: string;
    peakMarkerType?: string;
    peakMarkerSegmentId?: string | null;
    position?: number;
  };
}) {
  if (typeof cx !== 'number' || typeof cy !== 'number') {
    return null;
  }

  const color = payload?.peakMarkerSeverity?.toLowerCase() === 'major' ? '#ef4444' : '#f59e0b';
  const label = `${payload?.peakMarkerType ?? 'peak'}-${payload?.peakMarkerSegmentId ?? payload?.position}`;
  const markerTestId = `tension-peak-marker-${payload?.peakMarkerSegmentId ?? payload?.position ?? 'unknown'}`;
  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill={color} opacity={0.15} />
      <circle cx={cx} cy={cy} r={3} fill={color} stroke="#fff" strokeWidth={2} data-testid={markerTestId} />
      <text
        x={cx + 8}
        y={cy - 8}
        fill={color}
        fontSize={10}
        textAnchor="start"
        dominantBaseline="middle"
      >
        {label}
      </text>
    </g>
  );
}

export function ProjectDashboardsPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);
  const tensionGraphQuery = useTensionGraphQuery(projectId, runId);
  const characterAnalyticsQuery = useCharacterAnalyticsQuery(projectId, runId);
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

  const peakMarkerSeries = useMemo(
    () => (showSmoothed ? normalizePeakMarkers(tensionGraphQuery.data?.peak_markers) : []),
    [showSmoothed, tensionGraphQuery.data],
  );
  const plateauOverlays = useMemo(
    () => (showSmoothed ? normalizePlateauOverlays(tensionGraphQuery.data?.plateau_regions) : []),
    [showSmoothed, tensionGraphQuery.data],
  );

  const chartData = useMemo(() => (showSmoothed ? smoothedSeries : rawSeries).slice(0, 20), [showSmoothed, rawSeries, smoothedSeries]);
  const chartMaxPosition = chartData.length > 0 ? chartData[chartData.length - 1].position : 0;
  const peakMarkersByPosition = useMemo(() => {
    const markersByPosition = new Map<number, PeakMarkerPoint>();
    for (const marker of peakMarkerSeries) {
      markersByPosition.set(marker.position, marker);
    }
    return markersByPosition;
  }, [peakMarkerSeries]);
  const filteredPeakMarkerSeries = useMemo(
    () =>
      peakMarkerSeries.filter((peak) => peak.position >= 1 && (chartMaxPosition === 0 || peak.position <= chartMaxPosition + 1)),
    [peakMarkerSeries, chartMaxPosition],
  );
  const filteredPlateauOverlays = useMemo(
    () =>
      plateauOverlays.filter(
        (region) =>
          region.startPosition >= 1 &&
          (chartMaxPosition === 0 || region.startPosition <= chartMaxPosition + 1) &&
          region.endPosition >= 1,
      ),
    [plateauOverlays, chartMaxPosition],
  );
  const chartDataWithPeakOverlays = useMemo(() => {
    return chartData.map((point) => {
      const marker = peakMarkersByPosition.get(point.position);
      return {
        ...point,
        peakTension: marker ? marker.tension : null,
        peakMarkerSegmentId: marker ? marker.segmentId : null,
        peakMarkerType: marker ? marker.peakType : null,
        peakMarkerSeverity: marker ? marker.severity : null,
      };
    });
  }, [chartData, peakMarkersByPosition]);

  const maxTension = computeMax(chartData);
  const avgTension = computeAverage(chartData);
  const characterProminenceRows = useMemo(
    () => buildCharacterProminenceRows(characterAnalyticsQuery.data ?? null),
    [characterAnalyticsQuery.data],
  );
  const trendCharacters = useMemo(() => characterProminenceRows.slice(0, 3).map((item) => item.name), [characterProminenceRows]);
  const trendSeries = useMemo(
    () => buildCharacterTrendSeries(characterAnalyticsQuery.data ?? null, trendCharacters),
    [characterAnalyticsQuery.data, trendCharacters],
  );

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
              <XAxis dataKey="position" tickFormatter={(value) => `S ${value}`} />
              <YAxis domain={[0, 1]} />
              {filteredPlateauOverlays.map((region) => (
                <ReferenceArea
                  key={region.key}
                  x1={region.startPosition}
                  x2={region.endPosition}
                  y1={region.yMin}
                  y2={region.yMax}
                  fill="rgba(21, 115, 230, 0.16)"
                  fillOpacity={0.3}
                  stroke="rgba(21, 115, 230, 0.35)"
                  strokeOpacity={0.4}
                />
              ))}
              <Tooltip />
              <Line dataKey="tension" dot={false} stroke="#1473e6" strokeWidth={2.5} type="monotone" />
              <Line
                data={chartDataWithPeakOverlays}
                dataKey="peakTension"
                type="monotone"
                stroke="transparent"
                strokeWidth={0}
                dot={<PeakMarkerPointShape />}
                activeDot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            </LineChart>
          </div>

          {showSmoothed && (filteredPeakMarkerSeries.length > 0 || filteredPlateauOverlays.length > 0) ? (
            <div className="space-y-4 border-t border-panel-border/50 pt-4 text-sm">
              <div className="grid gap-1">
                <p className="font-medium text-foreground">Peak markers</p>
                {filteredPeakMarkerSeries.length > 0 ? (
                  <ul className="space-y-1 text-muted-foreground">
                    {filteredPeakMarkerSeries.map((marker, index) => (
                      <li key={`${marker.segmentId ?? marker.position}-${index}`}>
                        {marker.segmentId ?? `S ${marker.position}`}: {marker.peakType} ({marker.severity}) at{' '}
                        {formatPercent(marker.tension)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">No peak markers available for this window.</p>
                )}
              </div>
              <div className="grid gap-1">
                <p className="font-medium text-foreground">Plateau overlays</p>
                {filteredPlateauOverlays.length > 0 ? (
                  <ul className="space-y-1 text-muted-foreground">
                    {filteredPlateauOverlays.map((region, index) => (
                      <li key={`${region.key}-${index}`}>
                        {region.regionType}: S {region.startPosition} to S {region.endPosition} ({formatPercent(region.average)})
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">No plateau overlays available for this window.</p>
                )}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Character Prominence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">Top characters by mentions per 1,000 words and key appearance stats.</p>
          <div className="space-y-2 text-sm">
            {characterProminenceRows.slice(0, 5).map((character) => (
              <div
                key={character.name}
                className="grid gap-1 rounded border border-panel-border/50 bg-panel/40 px-3 py-2 sm:grid-cols-[1.5fr_1fr_1fr_1fr] sm:grid"
                data-testid={`dashboards-character-prominence-${character.name.replace(/\s+/g, '-')}`}
              >
                <p className="font-medium text-foreground sm:col-span-1">{character.name}</p>
                <p className="text-muted-foreground">Prominence: {character.mentionsPer1000Words.toFixed(2)}</p>
                <p className="text-muted-foreground">
                  Total mentions: <span className="font-medium text-foreground">{character.totalMentions}</span>
                </p>
                <p className="text-muted-foreground">
                  Dialogue lines: <span className="font-medium text-foreground">{character.dialogueLineCount}</span>
                </p>
              </div>
            ))}
            {characterProminenceRows.length === 0 ? <p className="text-sm text-muted-foreground">No character analytics available.</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Character Mention Trends</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {trendSeries.length > 0 && trendCharacters.length > 0 ? (
            <>
              <p className="text-sm text-muted-foreground">Per-chapter mention trajectory for top characters.</p>
              <div className="h-[20rem]">
                <LineChart width={900} height={280} data={trendSeries}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="chapterLabel" />
                  <YAxis allowDecimals />
                  <Tooltip />
                  <Legend />
                  {trendCharacters.map((name, index) => (
                    <Line
                      key={name}
                      dataKey={name}
                      name={name}
                      type="monotone"
                      stroke={CHARACTER_TREND_PALETTE[index % CHARACTER_TREND_PALETTE.length]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No character trend data available.</p>
          )}
          <div className="grid gap-1 text-xs text-muted-foreground">
            {characterProminenceRows.slice(0, 3).map((character, index) => (
              <p key={`${character.name}-trend-${index}`}>
                {character.name}: first appears in chapter {character.firstAppearanceChapter ?? '—'}, last appears in chapter{' '}
                {character.lastAppearanceChapter ?? '—'}.
              </p>
            ))}
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
