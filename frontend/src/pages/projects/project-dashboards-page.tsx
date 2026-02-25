import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useExportPayloadQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartNoAxesColumnIncreasing, LineChart as LineChartIcon, UsersRound } from 'lucide-react';

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

  return (
    <WorkflowPageShell
      step="Step 07"
      title="Dashboards"
      description="Explore visual analytics: tension, emotional polarity, dominance, and character trends."
      action={<Badge variant="outline">{exportPayloadQuery.data ? 'Using run export data' : 'Using fallback sample data'}</Badge>}
    >
      <div className="grid gap-4 lg:grid-cols-4">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ChartNoAxesColumnIncreasing className="size-4 text-primary" />
              Peak Tension
            </CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold tracking-tight text-foreground">
            {Math.max(...chartData.map((item) => item.tension)).toFixed(0)}
          </CardContent>
        </Card>
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <LineChartIcon className="size-4 text-primary" />
              Avg Valence
            </CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold tracking-tight text-foreground">
            {(chartData.reduce((acc, item) => acc + item.valence, 0) / chartData.length).toFixed(0)}
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UsersRound className="size-4 text-primary" />
              Dominance Snapshot
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              High dominance segments typically map to POV concentration or recurring speaker clusters.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Tension Curve</CardTitle>
          </CardHeader>
          <CardContent className="h-[20rem]">
            <ResponsiveContainer height="100%" width="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="chapter" />
                <YAxis />
                <Tooltip />
                <Line dataKey="tension" dot={false} stroke="#1473e6" strokeWidth={2.5} type="monotone" />
                <Line dataKey="valence" dot={false} stroke="#12a594" strokeWidth={2} type="monotone" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Chapter Focus</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {chartData.slice(0, 8).map((item) => (
              <div key={item.chapter} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-xl border bg-background/70 px-3 py-2 text-sm">
                <span className="font-medium text-foreground">{item.chapter}</span>
                <span className="text-muted-foreground">T {item.tension}</span>
                <span className="text-muted-foreground">D {item.dominance}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Emotion</CardTitle>
          </CardHeader>
          <CardContent className="h-60">
            <ResponsiveContainer height="100%" width="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="chapter" />
                <YAxis />
                <Tooltip />
                <Line dataKey="valence" dot={false} stroke="#1d4ed8" strokeWidth={2} type="monotone" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Character</CardTitle>
          </CardHeader>
          <CardContent className="h-60">
            <ResponsiveContainer height="100%" width="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="chapter" />
                <YAxis />
                <Tooltip />
                <Line dataKey="dominance" dot={false} stroke="#b45309" strokeWidth={2} type="monotone" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
