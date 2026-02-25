import { useMemo } from 'react';
import type { ComponentType } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { BookAudio, FlaskConical, PenSquare, SlidersHorizontal } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { useModeCatalogQuery, useRunDetailQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';

const MODE_COPY: Record<string, { title: string; description: string; icon: ComponentType<{ className?: string }> }> = {
  audiobook: {
    title: 'Audiobook',
    description: 'Voice-forward segmentation, narration/dialogue polish, and export-first flow.',
    icon: BookAudio,
  },
  academic: {
    title: 'Academic',
    description: 'Evidence-rich tagging, stable metadata traces, and analytical output confidence.',
    icon: FlaskConical,
  },
  author: {
    title: 'Author',
    description: 'Revision-friendly diagnostics, pacing notes, and character consistency checks.',
    icon: PenSquare,
  },
  custom: {
    title: 'Custom',
    description: 'Manual profile where each pipeline behavior is tuned per project requirements.',
    icon: SlidersHorizontal,
  },
};

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
  const canSelectMode = projectId !== null && chapterCount !== null;
  const hasExplicitModeSelection = selectedMode !== null;
  const modeCatalogQuery = useModeCatalogQuery(projectId !== null);
  const runDetailQuery = useRunDetailQuery(projectId, runId);

  const modeOptions = useMemo(() => {
    if (modeCatalogQuery.data?.modes?.length) {
      return modeCatalogQuery.data.modes;
    }
    return ['audiobook', 'academic', 'author', 'custom'];
  }, [modeCatalogQuery.data]);

  const effectiveMode = selectedMode ?? modeCatalogQuery.data?.default_mode ?? 'audiobook';
  const runModeSnapshot = runDetailQuery.data?.config?.mode;

  function handleModeChange(nextMode: string) {
    setSelectedMode(nextMode);
    toast.success(`Mode set to ${nextMode}.`);
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
      <div className="grid gap-4 lg:grid-cols-3">
        {modeOptions.map((mode) => {
          const modeMeta = MODE_COPY[mode] ?? MODE_COPY.custom;
          const Icon = modeMeta.icon;
          const isSelected = effectiveMode === mode;
          return (
            <button
              key={mode}
              className={[
                'group nipe-panel flex flex-col items-start gap-3 p-4 text-left transition duration-200',
                isSelected ? 'border-primary/40 bg-primary/6' : 'hover:border-primary/30 hover:bg-primary/3',
                !canSelectMode ? 'pointer-events-none opacity-55' : '',
              ].join(' ')}
              onClick={() => handleModeChange(mode)}
              type="button"
            >
              <span className="grid size-10 place-items-center rounded-xl bg-secondary text-primary">
                <Icon className="size-5" />
              </span>
              <div>
                <h3 className="text-base font-semibold text-panel-foreground">{modeMeta.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{modeMeta.description}</p>
              </div>
              <Badge variant={isSelected ? 'default' : 'outline'}>{isSelected ? 'Selected' : 'Choose'}</Badge>
            </button>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mode Control</CardTitle>
          <CardDescription>Mode control is locked until ingestion succeeds and chapter count is available.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <div className="grid gap-2">
            <Label htmlFor="mode-select">Select mode</Label>
            <NativeSelect
              id="mode-select"
              data-testid="mode-select"
              disabled={!canSelectMode || modeCatalogQuery.isLoading}
              value={effectiveMode}
              onChange={(event) => handleModeChange(event.target.value)}
            >
              {modeOptions.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </NativeSelect>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant={canSelectMode ? 'default' : 'outline'}>{canSelectMode ? 'Unlocked' : 'Locked'}</Badge>
            <Badge variant={hasExplicitModeSelection ? 'default' : 'secondary'}>
              Selection: {hasExplicitModeSelection ? 'chosen' : 'required'}
            </Badge>
            <Badge variant="outline">Run snapshot: {typeof runModeSnapshot === 'string' ? runModeSnapshot : 'not run yet'}</Badge>
            <Badge variant="outline">Chapter count: {chapterCount ?? 'n/a'}</Badge>
          </div>

          {!canSelectMode ? (
            <p className="text-sm text-muted-foreground lg:col-span-2">
              Ingest chapters in <strong>/projects/new</strong> before selecting a mode.
            </p>
          ) : null}

          {canSelectMode && !hasExplicitModeSelection ? (
            <p className="text-sm text-muted-foreground lg:col-span-2" data-testid="mode-required-hint">
              Choose a mode from the selector or a mode card to unlock downstream pipeline execution.
            </p>
          ) : null}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
