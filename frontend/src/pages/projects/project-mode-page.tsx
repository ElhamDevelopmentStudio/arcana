import { useMemo } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import {
  useModeCatalogQuery,
  useProjectSetupStatusQuery,
  useRunDetailQuery,
  useSwitchModeMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';

export function ProjectModePage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const chapterCount = useWorkspaceStore((state) => state.chapterCount);
  const selectedMode = useWorkspaceStore((state) => state.selectedMode);
  const runId = useWorkspaceStore((state) => state.runId);
  const setSelectedMode = useWorkspaceStore((state) => state.setSelectedMode);

  const projectId = routeProjectId ?? storeProjectId;
  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const setupSteps = setupStatusQuery.data?.steps ?? [];
  const ingestionStepReady = setupSteps.some((step) => step.step_id === 'ingestion' && step.ready);
  const canSelectMode = projectId !== null && (chapterCount !== null || ingestionStepReady);
  const hasExplicitModeSelection = selectedMode !== null;
  const modeCatalogQuery = useModeCatalogQuery(projectId !== null);
  const runDetailQuery = useRunDetailQuery(projectId, runId);
  const switchModeMutation = useSwitchModeMutation(projectId);

  const modeOptions = useMemo(() => {
    if (modeCatalogQuery.data?.modes?.length) {
      return modeCatalogQuery.data.modes;
    }
    return ['audiobook', 'academic', 'author', 'custom'];
  }, [modeCatalogQuery.data]);

  const effectiveMode = selectedMode ?? modeCatalogQuery.data?.default_mode ?? 'audiobook';
  const runModeSnapshot = runDetailQuery.data?.config?.mode;
  const selectedProfile = modeCatalogQuery.data?.mode_profiles?.[effectiveMode];

  async function handleModeChange(nextMode: string) {
    if (!canSelectMode || projectId === null) {
      return;
    }

    try {
      const response = await switchModeMutation.trigger({ mode: nextMode });
      setSelectedMode(response.selected_mode);
      if (response.stale_runs_marked > 0) {
        toast.success(
          `Mode set to ${response.selected_mode}. ${response.stale_runs_marked} previous run(s) marked stale.`,
        );
      } else {
        toast.success(`Mode set to ${response.selected_mode}.`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to switch mode');
    }
  }

  return (
    <WorkflowPageShell
      step="Step 02"
      title="Mode Selection"
      description="Choose the run mode after ingestion succeeds. This page is exclusively for selecting and confirming mode context."
      action={
        projectId !== null ? (
          <Button
            data-testid="mode-continue-button"
            disabled={!canSelectMode || !hasExplicitModeSelection}
            onClick={() => navigate(projectRoute(projectId, 'characters'))}
          >
            Continue to Character Map
          </Button>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Mode Control</CardTitle>
          <CardDescription>Select exactly one mode. No other setup belongs on this page.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
              <Label htmlFor="mode-select">Select mode</Label>
              <NativeSelect
                id="mode-select"
                data-testid="mode-select"
                disabled={!canSelectMode || modeCatalogQuery.isLoading || switchModeMutation.isMutating}
                value={effectiveMode}
                onChange={(event) => void handleModeChange(event.target.value)}
              >
              {modeOptions.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </NativeSelect>
          </div>

          <div className="grid gap-1 text-sm text-muted-foreground">
            <p>Mode selector: {canSelectMode ? 'unlocked' : 'locked until ingestion is complete'}.</p>
            <p>Current selection: {hasExplicitModeSelection ? selectedMode : 'not selected'}.</p>
            <p>Detected chapters: {chapterCount ?? (ingestionStepReady ? 'ingested (count pending refresh)' : 'n/a')}.</p>
            <p>Last run mode snapshot: {typeof runModeSnapshot === 'string' ? runModeSnapshot : 'none'}.</p>
          </div>

          {selectedProfile ? (
            <div className="grid gap-1 rounded-xl bg-muted/45 px-3 py-2 text-sm text-muted-foreground" data-testid="mode-profile-summary">
              <p>
                Default max segment chars: <strong className="text-foreground">{selectedProfile.max_segment_chars}</strong>
              </p>
              <p>
                Default provider: <strong className="text-foreground">{selectedProfile.provider_name}</strong>
              </p>
              <p>
                Default daily call cap: <strong className="text-foreground">{selectedProfile.max_calls_per_day}</strong>
              </p>
              <p className="text-xs">{selectedProfile.profile_intent}</p>
            </div>
          ) : null}

          {!canSelectMode ? (
            <p className="text-sm text-muted-foreground">
              Ingest chapters in <strong>/projects/new</strong> before selecting a mode.
            </p>
          ) : null}

          {canSelectMode && !hasExplicitModeSelection ? (
            <p className="text-sm text-muted-foreground" data-testid="mode-required-hint">
              Choose a mode from the selector to unlock downstream pipeline execution.
            </p>
          ) : null}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
