import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { AlertTriangle, RotateCcw, Clock, ToggleLeft, ToggleRight } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import {
  useProjectDetailQuery,
  useUpdateProjectMetadataMutation,
  useArchiveProjectMutation,
  useRestoreProjectMutation,
  useProjectLLMSettingsQuery,
  useLLMProvidersQuery,
  useUpdateLLMProviderStatusMutation,
  useProjectActivityTimelineQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-white/5 py-4 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function ProjectSettingsPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  const detailQuery = useProjectDetailQuery(projectId);
  const llmSettingsQuery = useProjectLLMSettingsQuery(projectId);
  const providersQuery = useLLMProvidersQuery(projectId !== null);
  const timelineQuery = useProjectActivityTimelineQuery(projectId, { page: 1, page_size: 10 });
  const updateMetaMutation = useUpdateProjectMetadataMutation(projectId);
  const archiveMutation = useArchiveProjectMutation(projectId);
  const restoreMutation = useRestoreProjectMutation(projectId);
  const updateProviderMutation = useUpdateLLMProviderStatusMutation(projectId);

  const [title, setTitle] = useState('');
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false);
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);

  const currentTitle = detailQuery.data?.title ?? '';
  const llmEnabled = llmSettingsQuery.data?.llm_enabled ?? false;
  const providers = providersQuery.data?.providers ?? [];
  const lifecycleState = detailQuery.data?.lifecycle_state ?? 'draft';
  const isArchived = lifecycleState === 'archived';
  const isBusy = updateMetaMutation.isMutating || archiveMutation.isMutating || restoreMutation.isMutating;
  const timelineItems = timelineQuery.data?.items ?? [];

  async function handleSaveTitle() {
    if (!title.trim()) { toast.error('Title cannot be empty.'); return; }
    try {
      await updateMetaMutation.trigger({ title: title.trim() });
      toast.success('Project name updated.');
      setTitle('');
      await detailQuery.mutate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Update failed');
    }
  }

  async function handleArchive() {
    try {
      await archiveMutation.trigger();
      toast.success('Project archived.');
      navigate('/dashboard');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Archive failed');
    }
  }

  async function handleRestore() {
    try {
      await restoreMutation.trigger();
      toast.success('Project restored.');
      await detailQuery.mutate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Restore failed');
    }
  }

  async function toggleProvider(providerName: string, currentEnabled: boolean) {
    try {
      await updateProviderMutation.trigger({ provider_name: providerName, enabled: !currentEnabled });
      await providersQuery.mutate();
      toast.success(`${providerName} ${!currentEnabled ? 'enabled' : 'disabled'}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update provider');
    }
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Settings`}
      title="Settings"
      description="Manage project configuration and lifecycle."
    >
      <div className="max-w-2xl space-y-2">
        {/* General */}
        <div className="rounded-xl border border-white/10 bg-card px-5">
          <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">General</p>
          <SettingRow label="Project name" description={`Current: ${currentTitle}`}>
            <div className="flex gap-2">
              <Input
                className="w-48"
                data-testid="settings-title-input"
                onChange={(e) => setTitle(e.target.value)}
                placeholder={currentTitle}
                value={title}
              />
              <Button
                data-testid="settings-save-title-button"
                disabled={isBusy || !title.trim()}
                onClick={() => void handleSaveTitle()}
                size="sm"
                variant="outline"
              >
                Save
              </Button>
            </div>
          </SettingRow>
          <SettingRow label="Project ID" description="Immutable identifier">
            <span className="font-mono text-sm text-muted-foreground">#{projectId}</span>
          </SettingRow>
          <SettingRow label="Lifecycle state">
            <span className={cn('text-sm font-medium capitalize', isArchived ? 'text-muted-foreground' : 'text-foreground')}>
              {lifecycleState}
            </span>
          </SettingRow>
        </div>

        {/* LLM */}
        <div className="rounded-xl border border-white/10 bg-card px-5">
          <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">LLM</p>
          <SettingRow label="LLM processing" description="Whether LLM analysis is enabled for this project">
            <span className={`text-sm font-medium ${llmEnabled ? 'text-green-400' : 'text-muted-foreground'}`}>
              {llmEnabled ? 'Enabled' : 'Disabled'}
            </span>
          </SettingRow>
          {providers.length > 0 && (
            <SettingRow label="Providers" description="Toggle individual LLM providers on or off">
              <div className="flex flex-col gap-2">
                {providers.map((p) => (
                  <div className="flex items-center gap-3" key={p.provider}>
                    <span className="text-sm text-foreground w-28">{p.provider}</span>
                    <button
                      aria-label={p.enabled ? `Disable ${p.provider}` : `Enable ${p.provider}`}
                      className={cn(
                        'flex items-center gap-1.5 text-xs font-medium transition-colors',
                        p.enabled ? 'text-green-400' : 'text-muted-foreground',
                      )}
                      data-testid={`toggle-provider-${p.provider}`}
                      disabled={updateProviderMutation.isMutating}
                      onClick={() => void toggleProvider(p.provider, p.enabled)}
                      type="button"
                    >
                      {p.enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                      {p.enabled ? 'On' : 'Off'}
                    </button>
                  </div>
                ))}
              </div>
            </SettingRow>
          )}
        </div>

        {/* Activity timeline */}
        {timelineItems.length > 0 && (
          <div className="rounded-xl border border-white/10 bg-card px-5" data-testid="activity-timeline">
            <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Activity Timeline</p>
            <div className="py-3 space-y-0">
              {timelineItems.map((item) => (
                <div className="flex items-start gap-3 border-b border-white/5 py-3 last:border-0" key={item.event_id}>
                  <Clock className="mt-0.5 shrink-0 text-muted-foreground/40" size={13} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-foreground">{item.event_type.replace(/_/g, ' ')}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.actor}
                      {item.run_id ? ` · run #${item.run_id}` : ''}
                      {' · '}
                      {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
                    </p>
                  </div>
                </div>
              ))}
              {(timelineQuery.data?.has_next_page) && (
                <p className="py-2 text-center text-xs text-muted-foreground">Showing last 10 events</p>
              )}
            </div>
          </div>
        )}

        {/* Danger zone */}
        <div className="rounded-xl border border-destructive/30 bg-card px-5" data-testid="settings-danger-zone">
          <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-destructive/60">Danger Zone</p>
          {isArchived ? (
            <SettingRow
              label="Restore project"
              description="Restore this project from archived state back to active."
            >
              <Button
                data-testid="restore-project-button"
                disabled={isBusy}
                onClick={() => setRestoreDialogOpen(true)}
                size="sm"
                variant="outline"
              >
                <RotateCcw size={13} />
                Restore
              </Button>
            </SettingRow>
          ) : (
            <SettingRow
              label="Archive project"
              description="Hides this project from the dashboard. Reversible."
            >
              <Button
                data-testid="archive-project-button"
                disabled={isBusy}
                onClick={() => setArchiveDialogOpen(true)}
                size="sm"
                variant="destructive"
              >
                <AlertTriangle size={13} />
                Archive
              </Button>
            </SettingRow>
          )}
        </div>
      </div>

      <AlertDialog onOpenChange={setArchiveDialogOpen} open={archiveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive this project?</AlertDialogTitle>
            <AlertDialogDescription>
              The project will be hidden from the dashboard. You can restore it later from Settings.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="archive-confirm-button"
              disabled={isBusy}
              onClick={() => void handleArchive()}
            >
              {archiveMutation.isMutating ? 'Archiving…' : 'Archive project'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog onOpenChange={setRestoreDialogOpen} open={restoreDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Restore this project?</AlertDialogTitle>
            <AlertDialogDescription>
              The project will be moved back to active state and become visible on the dashboard.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="restore-confirm-button"
              disabled={isBusy}
              onClick={() => void handleRestore()}
            >
              {restoreMutation.isMutating ? 'Restoring…' : 'Restore project'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </WorkflowPageShell>
  );
}
