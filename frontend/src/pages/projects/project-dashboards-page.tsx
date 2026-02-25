import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

type DashboardPoint = {
  chapter: string;
  tension: number;
  valence: number;
  dominance: number;
};

function buildFallbackPoints(): DashboardPoint[] {
  return Array.from({ length: 12 }, (_, index) => ({
    chapter: `Ch ${index + 1}`,
    tension: 20 + (index % 5) * 12 + (index * 3) % 9,
    valence: -20 + ((index * 7) % 40),
    dominance: 15 + ((index * 11) % 60),
  }));
}

export function ProjectDashboardsPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const runId = useWorkspaceStore((state) => state.runId);

  const projectId = routeProjectId ?? storeProjectId;
  const exportPayloadQuery = useExportPayloadQuery(projectId, runId);

  const chartData = useMemo<DashboardPoint[]>(() => {
    const segments = exportPayloadQuery.data?.segments;
    if (!segments || segments.length === 0) {
      return buildFallbackPoints();
    }

    return segments.slice(0, 20).map((segment, index) => {
      const text = String(segment.original_text ?? segment.phonetic_text ?? '');
      const raw = text.length > 0 ? text : JSON.stringify(segment);
      const base = raw.length;
      return {
        chapter: `S ${index + 1}`,
        tension: Math.min(100, 15 + (base % 85)),
        valence: -50 + (base % 100),
        dominance: Math.min(100, 10 + ((base * 3) % 90)),
      };
    });
  }, [exportPayloadQuery.data]);

  const maxTension = Math.max(...chartData.map((item) => item.tension));
  const avgValence = chartData.reduce((acc, item) => acc + item.valence, 0) / chartData.length;
  const avgDominance = chartData.reduce((acc, item) => acc + item.dominance, 0) / chartData.length;

  return (
    <WorkflowPageShell
      step="Step 07"
      title="Dashboards"
      description="Explore visual analytics: tension, emotional polarity, dominance, and character trends."
      action={
        <p className="text-sm text-muted-foreground">{exportPayloadQuery.data ? 'Data source: run export' : 'Data source: fallback sample'}</p>
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Narrative Trend</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 text-sm text-muted-foreground lg:grid-cols-3">
            <p>
              Peak tension: <strong className="text-foreground">{maxTension.toFixed(0)}</strong>
            </p>
            <p>
              Average valence: <strong className="text-foreground">{avgValence.toFixed(0)}</strong>
            </p>
            <p>
              Average dominance: <strong className="text-foreground">{avgDominance.toFixed(0)}</strong>
            </p>
          </div>

          <div className="h-[20rem]">
            <ResponsiveContainer height="100%" width="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="chapter" />
                <YAxis />
                <Tooltip />
                <Line dataKey="tension" dot={false} stroke="#1473e6" strokeWidth={2.5} type="monotone" />
                <Line dataKey="valence" dot={false} stroke="#12a594" strokeWidth={2} type="monotone" />
                <Line dataKey="dominance" dot={false} stroke="#b45309" strokeWidth={2} type="monotone" />
              </LineChart>
            </ResponsiveContainer>
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
                className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 py-1.5 [&:not(:last-child)]:border-b [&:not(:last-child)]:border-panel-border/50"
              >
                <span className="font-medium text-foreground">{item.chapter}</span>
                <span className="text-muted-foreground">T {item.tension}</span>
                <span className="text-muted-foreground">V {item.valence}</span>
                <span className="text-muted-foreground">D {item.dominance}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
