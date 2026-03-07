import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { BookOpen, GraduationCap, Pen, Sliders, Check } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  useModeCatalogQuery,
  useProjectSetupStatusQuery,
  useSwitchModeMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';

const MODE_META: Record<string, { icon: React.ComponentType<{ size?: number; className?: string }>; description: string }> = {
  audiobook: { icon: BookOpen, description: 'Optimized for novels and narrative fiction with multi-character voice support.' },
  academic:  { icon: GraduationCap, description: 'Structured processing for papers, theses, and scholarly content.' },
  author:    { icon: Pen, description: 'Balanced pipeline tuned for authored manuscripts and memoirs.' },
  custom:    { icon: Sliders, description: 'Full manual control of all pipeline parameters and thresholds.' },
};

export function ProjectModePage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const selectedMode = useWorkspaceStore((state) => state.selectedMode);
  const setSelectedMode = useWorkspaceStore((state) => state.setSelectedMode);
  const [pendingMode, setPendingMode] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const projectId = routeProjectId ?? storeProjectId;
  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const modeCatalogQuery = useModeCatalogQuery(projectId !== null);
  const switchModeMutation = useSwitchModeMutation(projectId);

  const ingestionReady = setupStatusQuery.data?.steps?.some((s) => s.step_id === 'ingestion' && s.ready) ?? false;
  const canSelectMode = projectId !== null && ingestionReady;
  const effectiveMode = selectedMode ?? modeCatalogQuery.data?.default_mode ?? 'audiobook';

  const modeOptions = useMemo(() => {
    const catalog = modeCatalogQuery.data?.modes;
    return catalog?.length ? catalog : ['audiobook', 'academic', 'author', 'custom'];
  }, [modeCatalogQuery.data]);

  async function handleConfirm() {
    if (!pendingMode || !projectId) return;
    try {
      const res = await switchModeMutation.trigger({ mode: pendingMode });
      setSelectedMode(res.selected_mode);
      toast.success(`Mode set to ${res.selected_mode}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to switch mode');
    } finally {
      setPendingMode(null);
      setConfirmOpen(false);
    }
  }

  function selectMode(mode: string) {
    if (!canSelectMode || mode === effectiveMode) return;
    setPendingMode(mode);
    setConfirmOpen(true);
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Mode`}
      title="Processing Mode"
      description="Choose the pipeline mode that best matches your source content."
      action={
        projectId !== null && selectedMode ? (
          <Button
            data-testid="mode-continue-button"
            onClick={() => navigate(projectRoute(projectId, 'characters'))}
          >
            Continue to Characters
          </Button>
        ) : undefined
      }
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="mode-card-grid">
        {modeOptions.map((mode) => {
          const meta = MODE_META[mode] ?? { icon: Sliders, description: 'Custom processing mode.' };
          const Icon = meta.icon;
          const isActive = effectiveMode === mode;
          return (
            <button
              className={cn(
                'flex flex-col gap-3 rounded-xl border p-4 text-left transition-all duration-150',
                canSelectMode ? 'cursor-pointer' : 'cursor-not-allowed opacity-50',
                isActive ? 'border-white/50 bg-white/5' : 'border-white/10 hover:border-white/20',
              )}
              data-testid={`mode-card-${mode}`}
              disabled={!canSelectMode}
              key={mode}
              onClick={() => selectMode(mode)}
              type="button"
            >
              <div className="flex items-start justify-between">
                <Icon className="text-muted-foreground" size={18} />
                {isActive && <Check className="text-foreground" size={14} />}
              </div>
              <div>
                <p className="text-sm font-semibold capitalize text-foreground">{mode}</p>
                <p className="mt-1 text-xs text-muted-foreground">{meta.description}</p>
              </div>
            </button>
          );
        })}
      </div>

      {!canSelectMode && (
        <p className="text-sm text-muted-foreground" data-testid="mode-locked-hint">
          Complete source ingestion to unlock mode selection.
        </p>
      )}

      {modeCatalogQuery.data?.mode_profiles?.[effectiveMode] && (
        <div className="rounded-xl border border-white/10 bg-card p-4" data-testid="mode-profile-summary">
          <p className="mb-2 text-sm font-semibold text-foreground">Profile: {effectiveMode}</p>
          <dl className="space-y-1 text-sm">
            {[
              { label: 'Max segment chars', value: modeCatalogQuery.data.mode_profiles[effectiveMode].max_segment_chars },
              { label: 'Provider', value: modeCatalogQuery.data.mode_profiles[effectiveMode].provider_name },
              { label: 'Daily call cap', value: modeCatalogQuery.data.mode_profiles[effectiveMode].max_calls_per_day },
            ].map(({ label, value }) => (
              <div className="flex gap-2" key={label}>
                <dt className="w-36 shrink-0 text-muted-foreground">{label}</dt>
                <dd className="text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-xs text-muted-foreground">{modeCatalogQuery.data.mode_profiles[effectiveMode].profile_intent}</p>
        </div>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent data-testid="mode-switch-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Switch processing mode?</AlertDialogTitle>
            <AlertDialogDescription>
              Switching from <strong className="text-foreground">{effectiveMode}</strong> to{' '}
              <strong className="text-foreground">{pendingMode}</strong> will mark existing run outputs as stale.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="mode-switch-confirm-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="mode-switch-confirm-submit"
              disabled={switchModeMutation.isMutating}
              onClick={() => void handleConfirm()}
            >
              {switchModeMutation.isMutating ? 'Switching…' : 'Switch mode'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </WorkflowPageShell>
  );
}
