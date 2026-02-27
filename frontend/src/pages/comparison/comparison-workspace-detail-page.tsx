import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  useAddRunToComparisonWorkspaceMutation,
  useComparisonWorkspaceAlignedCurvesQuery,
  useComparisonWorkspaceComparativeDatasetMutation,
  useComparisonWorkspaceDetailQuery,
} from '@/features/workflow/api/workflow-hooks';
import { type FormEvent, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

function parseWorkspaceIdParam(value: string | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export function ComparisonWorkspaceDetailPage() {
  const params = useParams<{ workspace_id: string }>();
  const workspaceId = useMemo(() => parseWorkspaceIdParam(params.workspace_id), [params.workspace_id]);
  const workspaceDetailQuery = useComparisonWorkspaceDetailQuery(workspaceId);
  const addRunMutation = useAddRunToComparisonWorkspaceMutation(workspaceId);
  const [projectIdInput, setProjectIdInput] = useState('');
  const [runIdInput, setRunIdInput] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null);
  const [metricsInput, setMetricsInput] = useState('');
  const [alignedPointsInput, setAlignedPointsInput] = useState('');
  const [curvesFilterError, setCurvesFilterError] = useState<string | null>(null);
  const [curvesFilters, setCurvesFilters] = useState<{ metrics?: string[]; aligned_points?: number }>({});
  const alignedCurvesQuery = useComparisonWorkspaceAlignedCurvesQuery(workspaceId, curvesFilters);
  const comparativeDatasetMutation = useComparisonWorkspaceComparativeDatasetMutation(workspaceId);
  const [comparativeDatasetError, setComparativeDatasetError] = useState<string | null>(null);
  const [comparativeDatasetSummary, setComparativeDatasetSummary] = useState<{
    workspace_id: number;
    run_count: number;
    aligned_points: number;
    metrics_count: number;
    runs_count: number;
    generated_at: string;
  } | null>(null);

  async function handleLinkRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLinkError(null);
    setLinkSuccess(null);

    if (workspaceId === null) {
      setLinkError('A valid workspace ID is required before linking runs.');
      return;
    }

    const parsedProjectId = Number.parseInt(projectIdInput.trim(), 10);
    const parsedRunId = Number.parseInt(runIdInput.trim(), 10);

    if (!Number.isInteger(parsedProjectId) || parsedProjectId <= 0) {
      setLinkError('Enter a valid numeric project ID.');
      return;
    }
    if (!Number.isInteger(parsedRunId) || parsedRunId <= 0) {
      setLinkError('Enter a valid numeric run ID.');
      return;
    }

    try {
      await addRunMutation.trigger({
        project_id: parsedProjectId,
        run_id: parsedRunId,
      });
      await workspaceDetailQuery.mutate();
      setRunIdInput('');
      setLinkSuccess(`Run #${parsedRunId} linked to workspace #${workspaceId}.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to link run to comparison workspace.';
      setLinkError(message);
    }
  }

  function handleApplyCurvesFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCurvesFilterError(null);

    const parsedMetrics = Array.from(
      new Set(
        metricsInput
          .split(',')
          .map((metric) => metric.trim())
          .filter((metric) => metric.length > 0),
      ),
    );
    const trimmedAlignedPointsInput = alignedPointsInput.trim();
    let parsedAlignedPoints: number | undefined;
    if (trimmedAlignedPointsInput.length > 0) {
      const parsedValue = Number.parseInt(trimmedAlignedPointsInput, 10);
      if (!Number.isInteger(parsedValue) || parsedValue <= 0) {
        setCurvesFilterError('Aligned points must be a positive integer.');
        return;
      }
      parsedAlignedPoints = parsedValue;
    }

    setCurvesFilters({
      metrics: parsedMetrics.length > 0 ? parsedMetrics : undefined,
      aligned_points: parsedAlignedPoints,
    });
  }

  async function handleFetchComparativeDataset() {
    setComparativeDatasetError(null);
    setComparativeDatasetSummary(null);
    try {
      const comparativeDataset = await comparativeDatasetMutation.trigger(curvesFilters);
      setComparativeDatasetSummary({
        workspace_id: comparativeDataset.workspace_id,
        run_count: comparativeDataset.run_count,
        aligned_points: comparativeDataset.aligned_points,
        metrics_count: comparativeDataset.metrics.length,
        runs_count: comparativeDataset.runs.length,
        generated_at: comparativeDataset.generated_at,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to retrieve comparative dataset export.';
      setComparativeDatasetError(message);
    }
  }

  return (
    <WorkflowPageShell
      step="Comparison"
      title="Comparison Workspace"
      description="Inspect a comparison workspace and the linked runs available for aligned analysis."
      action={
        workspaceId !== null ? (
          <Badge variant="outline">Workspace #{workspaceId}</Badge>
        ) : (
          <Badge variant="destructive">Invalid workspace ID</Badge>
        )
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Workspace Detail</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          {workspaceId === null ? <p>Provide a valid workspace ID in the route.</p> : null}
          {workspaceDetailQuery.isLoading ? <p>Loading comparison workspace...</p> : null}
          {workspaceDetailQuery.error ? <p className="text-destructive">{workspaceDetailQuery.error.message}</p> : null}

          {workspaceDetailQuery.data ? (
            <>
              <p>
                Workspace: <strong className="text-foreground">#{workspaceDetailQuery.data.workspace_id}</strong>
              </p>
              <p>
                Name: <strong className="text-foreground">{workspaceDetailQuery.data.name ?? 'Untitled workspace'}</strong>
              </p>
              <p>
                Linked runs: <strong className="text-foreground">{workspaceDetailQuery.data.run_count}</strong>
              </p>

              <form className="space-y-3 rounded-md border p-3" onSubmit={handleLinkRun}>
                <p className="text-sm font-medium text-foreground">Link run to workspace</p>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground" htmlFor="workspace-link-project-id">
                      Project ID
                    </label>
                    <Input
                      id="workspace-link-project-id"
                      data-testid="comparison-workspace-link-project-id-input"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={projectIdInput}
                      onChange={(event) => setProjectIdInput(event.target.value)}
                      placeholder="e.g. 123"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground" htmlFor="workspace-link-run-id">
                      Run ID
                    </label>
                    <Input
                      id="workspace-link-run-id"
                      data-testid="comparison-workspace-link-run-id-input"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={runIdInput}
                      onChange={(event) => setRunIdInput(event.target.value)}
                      placeholder="e.g. 456"
                    />
                  </div>
                </div>

                {linkError ? (
                  <p className="text-sm text-destructive" data-testid="comparison-workspace-link-error">{linkError}</p>
                ) : null}
                {linkSuccess ? (
                  <p className="text-sm text-foreground" data-testid="comparison-workspace-link-success">{linkSuccess}</p>
                ) : null}

                <Button
                  type="submit"
                  data-testid="comparison-workspace-link-run-button"
                  disabled={workspaceId === null || addRunMutation.isMutating}
                >
                  {addRunMutation.isMutating ? 'Linking run...' : 'Link run'}
                </Button>
              </form>

              <div className="space-y-3 rounded-md border p-3" data-testid="comparison-workspace-aligned-curves-panel">
                <p className="text-sm font-medium text-foreground">Aligned Curves Analysis</p>

                <form className="grid gap-3 md:grid-cols-[1fr_180px_auto]" onSubmit={handleApplyCurvesFilters}>
                  <div className="space-y-1">
                    <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground" htmlFor="workspace-curves-metrics">
                      Metrics (comma-separated)
                    </label>
                    <Input
                      id="workspace-curves-metrics"
                      data-testid="comparison-workspace-curves-metrics-input"
                      value={metricsInput}
                      onChange={(event) => setMetricsInput(event.target.value)}
                      placeholder="chapter_valence_mean, smoothed_tension_curve"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground" htmlFor="workspace-curves-aligned-points">
                      Aligned points
                    </label>
                    <Input
                      id="workspace-curves-aligned-points"
                      data-testid="comparison-workspace-curves-aligned-points-input"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={alignedPointsInput}
                      onChange={(event) => setAlignedPointsInput(event.target.value)}
                      placeholder="e.g. 32"
                    />
                  </div>

                  <div className="flex items-end">
                    <Button type="submit" data-testid="comparison-workspace-curves-apply-button">Apply filters</Button>
                  </div>
                </form>

                {curvesFilterError ? (
                  <p className="text-sm text-destructive" data-testid="comparison-workspace-curves-filter-error">
                    {curvesFilterError}
                  </p>
                ) : null}
                {alignedCurvesQuery.isLoading ? <p>Loading aligned curves...</p> : null}
                {alignedCurvesQuery.error ? (
                  <p className="text-sm text-destructive" data-testid="comparison-workspace-curves-error">
                    {alignedCurvesQuery.error.message}
                  </p>
                ) : null}

                {alignedCurvesQuery.data ? (
                  <>
                    <p>
                      Aligned points: <strong className="text-foreground">{alignedCurvesQuery.data.aligned_points}</strong>
                    </p>
                    <p>
                      Metrics returned: <strong className="text-foreground">{alignedCurvesQuery.data.metrics.length}</strong>
                    </p>

                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead>Runs</TableHead>
                          <TableHead>Points per run</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {alignedCurvesQuery.data.metrics.length === 0 ? (
                          <TableRow>
                            <TableCell className="text-muted-foreground" colSpan={3}>
                              No aligned metrics returned for current filters.
                            </TableCell>
                          </TableRow>
                        ) : (
                          alignedCurvesQuery.data.metrics.map((metric) => (
                            <TableRow key={metric.metric_id}>
                              <TableCell>{metric.metric_id}</TableCell>
                              <TableCell>{metric.points_per_run.length}</TableCell>
                              <TableCell>{metric.points_per_run[0]?.points.length ?? 0}</TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </>
                ) : null}
              </div>

              <div className="space-y-3 rounded-md border p-3" data-testid="comparison-workspace-comparative-dataset-panel">
                <p className="text-sm font-medium text-foreground">Comparative Dataset Export</p>
                <p className="text-xs text-muted-foreground">
                  Retrieve the comparative dataset JSON for this workspace using currently applied aligned-curves filters.
                </p>
                <Button
                  data-testid="comparison-workspace-export-fetch-button"
                  onClick={handleFetchComparativeDataset}
                  disabled={workspaceId === null || comparativeDatasetMutation.isMutating}
                >
                  {comparativeDatasetMutation.isMutating ? 'Retrieving export...' : 'Retrieve comparative dataset'}
                </Button>

                {comparativeDatasetError ? (
                  <p className="text-sm text-destructive" data-testid="comparison-workspace-export-error">
                    {comparativeDatasetError}
                  </p>
                ) : null}

                {comparativeDatasetSummary ? (
                  <div className="space-y-1 text-sm text-muted-foreground" data-testid="comparison-workspace-export-summary">
                    <p>
                      Workspace: <strong className="text-foreground">#{comparativeDatasetSummary.workspace_id}</strong>
                    </p>
                    <p>
                      Runs: <strong className="text-foreground">{comparativeDatasetSummary.run_count}</strong>
                    </p>
                    <p>
                      Aligned points: <strong className="text-foreground">{comparativeDatasetSummary.aligned_points}</strong>
                    </p>
                    <p>
                      Metrics: <strong className="text-foreground">{comparativeDatasetSummary.metrics_count}</strong>
                    </p>
                    <p>
                      Run entries: <strong className="text-foreground">{comparativeDatasetSummary.runs_count}</strong>
                    </p>
                    <p>
                      Generated at: <strong className="text-foreground">{comparativeDatasetSummary.generated_at}</strong>
                    </p>
                  </div>
                ) : null}
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Project</TableHead>
                    <TableHead>Run</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workspaceDetailQuery.data.runs.length === 0 ? (
                    <TableRow>
                      <TableCell className="text-muted-foreground" colSpan={3}>
                        No runs linked yet.
                      </TableCell>
                    </TableRow>
                  ) : (
                    workspaceDetailQuery.data.runs.map((run) => (
                      <TableRow key={`${run.project_id}-${run.run_id}`}>
                        <TableCell>
                          <p>
                            #{run.project_id}
                            {run.project_title ? ` (${run.project_title})` : ''}
                          </p>
                        </TableCell>
                        <TableCell>Run #{run.run_id}</TableCell>
                        <TableCell>{run.status}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </>
          ) : null}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
