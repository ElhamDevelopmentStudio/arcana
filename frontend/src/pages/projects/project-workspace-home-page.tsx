import { type FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ApiPanelError, ApiPanelLoading } from '@/components/ui/api-panel-state';
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
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  useArchiveProjectMutation,
  useProjectActivityTimelineQuery,
  useProjectAllowedActionsQuery,
  useProjectDetailQuery,
  useRestoreProjectMutation,
  useUpdateProjectMetadataMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectWorkspaceHomePage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;
  const projectDetailQuery = useProjectDetailQuery(projectId);
  const projectAllowedActionsQuery = useProjectAllowedActionsQuery(projectId);
  const [timelinePage, setTimelinePage] = useState(1);
  const timelinePageSize = 5;
  const projectTimelineQuery = useProjectActivityTimelineQuery(projectId, {
    page: timelinePage,
    page_size: timelinePageSize,
  });
  const [isArchiveConfirmOpen, setIsArchiveConfirmOpen] = useState(false);
  const [isRestoreConfirmOpen, setIsRestoreConfirmOpen] = useState(false);
  const [lifecycleTransitionConflict, setLifecycleTransitionConflict] = useState<string | null>(null);
  const archiveProjectMutation = useArchiveProjectMutation(projectId);
  const restoreProjectMutation = useRestoreProjectMutation(projectId);
  const updateProjectMetadataMutation = useUpdateProjectMetadataMutation(projectId);
  const [metadataTitle, setMetadataTitle] = useState('');
  const [metadataDescription, setMetadataDescription] = useState('');
  const [metadataTagsInput, setMetadataTagsInput] = useState('');

  const projectDetailErrorMessage =
    projectDetailQuery.error instanceof Error ? projectDetailQuery.error.message : 'Unable to load project detail.';
  const projectActionsErrorMessage =
    projectAllowedActionsQuery.error instanceof Error
      ? projectAllowedActionsQuery.error.message
      : 'Unable to load action gating metadata.';

  useEffect(() => {
    if (!projectDetailQuery.data) {
      return;
    }
    setMetadataTitle(projectDetailQuery.data.title ?? '');
    setMetadataDescription(projectDetailQuery.data.description ?? '');
    setMetadataTagsInput((projectDetailQuery.data.tags ?? []).join(', '));
  }, [projectDetailQuery.data]);

  if (projectId === null) {
    return (
      <Card data-testid="project-workspace-home-project-required">
        <CardHeader>
          <CardTitle>Project required</CardTitle>
          <CardDescription>Select or create a project before opening workspace home.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (projectDetailQuery.isLoading && projectDetailQuery.data === undefined) {
    return (
      <div data-testid="project-workspace-home-loading">
        <ApiPanelLoading description="Fetching project detail contract." title="Loading project detail" />
      </div>
    );
  }

  if (projectDetailQuery.error) {
    return (
      <div data-testid="project-workspace-home-error">
        <ApiPanelError
          description={projectDetailErrorMessage}
          onRetry={() => {
            void projectDetailQuery.mutate();
          }}
          retryLabel="Retry project detail"
          title="Project detail unavailable"
        />
      </div>
    );
  }

  async function handleMetadataSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    const normalizedTitle = metadataTitle.trim();
    const normalizedDescription = metadataDescription.trim();
    const normalizedTags = metadataTagsInput
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);

    if (!normalizedTitle) {
      toast.error('Project title is required.');
      return;
    }

    try {
      await updateProjectMetadataMutation.trigger({
        title: normalizedTitle,
        description: normalizedDescription.length > 0 ? normalizedDescription : null,
        tags: normalizedTags,
      });
      toast.success('Project metadata updated.');
      await projectDetailQuery.mutate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update metadata.');
    }
  }

  async function handleArchiveProject() {
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    setLifecycleTransitionConflict(null);
    try {
      await archiveProjectMutation.trigger();
      setIsArchiveConfirmOpen(false);
      toast.success('Project archived.');
      await Promise.all([
        projectAllowedActionsQuery.mutate(),
        projectDetailQuery.mutate(),
        projectTimelineQuery.mutate(),
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to archive project.';
      setLifecycleTransitionConflict(message);
      toast.error(message);
    }
  }

  async function handleRestoreProject() {
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    setLifecycleTransitionConflict(null);
    try {
      await restoreProjectMutation.trigger();
      setIsRestoreConfirmOpen(false);
      toast.success('Project restored.');
      await Promise.all([
        projectAllowedActionsQuery.mutate(),
        projectDetailQuery.mutate(),
        projectTimelineQuery.mutate(),
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to restore project.';
      setLifecycleTransitionConflict(message);
      toast.error(message);
    }
  }

  const allowedActions = projectAllowedActionsQuery.data?.allowed_actions ?? [];
  const isCommandAllowed = (action: string) => allowedActions.includes(action);

  return (
    <Card data-testid="project-workspace-home-ready">
      <CardHeader>
        <CardDescription data-testid="project-workspace-home-source-contract">
          From `GET /api/projects/{'{project_id}'}`
        </CardDescription>
        <CardTitle data-testid="project-workspace-home-title">{projectDetailQuery.data?.title ?? `Project #${projectId}`}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p data-testid="project-workspace-home-id">Project ID: {projectDetailQuery.data?.project_id ?? projectId}</p>
        <p data-testid="project-workspace-home-lifecycle">Lifecycle: {projectDetailQuery.data?.lifecycle_state ?? 'draft'}</p>
        <p data-testid="project-workspace-home-next-action">
          Next action: {projectDetailQuery.data?.next_required_action ?? 'none'}
        </p>
        <p data-testid="project-workspace-home-mode">Mode: {projectDetailQuery.data?.selected_mode ?? 'n/a'}</p>
        <form className="mt-4 space-y-3 rounded-lg border border-panel-border/70 p-3" data-testid="project-metadata-form" onSubmit={handleMetadataSubmit}>
          <p className="text-xs font-semibold tracking-wide text-foreground">Project metadata</p>
          <div className="grid gap-2">
            <Label htmlFor="project-metadata-title">Title</Label>
            <Input
              id="project-metadata-title"
              data-testid="project-metadata-title-input"
              onChange={(event) => setMetadataTitle(event.target.value)}
              value={metadataTitle}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="project-metadata-description">Description</Label>
            <Textarea
              id="project-metadata-description"
              data-testid="project-metadata-description-input"
              onChange={(event) => setMetadataDescription(event.target.value)}
              value={metadataDescription}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="project-metadata-tags">Tags (comma-separated)</Label>
            <Input
              id="project-metadata-tags"
              data-testid="project-metadata-tags-input"
              onChange={(event) => setMetadataTagsInput(event.target.value)}
              placeholder="arc, research"
              value={metadataTagsInput}
            />
          </div>
          <div className="flex justify-end">
            <Button data-testid="project-metadata-save-button" disabled={updateProjectMetadataMutation.isMutating} type="submit">
              {updateProjectMetadataMutation.isMutating ? 'Saving...' : 'Save metadata'}
            </Button>
          </div>
        </form>
        <div className="mt-4 space-y-3 rounded-lg border border-panel-border/70 p-3" data-testid="project-command-panel">
          <p className="text-xs font-semibold tracking-wide text-foreground">Action-gated command panel</p>
          {projectAllowedActionsQuery.isLoading && projectAllowedActionsQuery.data === undefined ? (
            <div data-testid="project-command-panel-loading">
              <ApiPanelLoading
                description="Fetching allowed actions for this project."
                title="Loading command panel"
              />
            </div>
          ) : projectAllowedActionsQuery.error ? (
            <div data-testid="project-command-panel-error">
              <ApiPanelError
                description={projectActionsErrorMessage}
                onRetry={() => {
                  void projectAllowedActionsQuery.mutate();
                }}
                retryLabel="Retry actions"
                title="Command panel unavailable"
              />
            </div>
          ) : (
            <>
              <p className="text-xs text-muted-foreground" data-testid="project-command-panel-next-action">
                Next action: {projectAllowedActionsQuery.data?.next_required_action ?? 'none'}
              </p>
              {projectAllowedActionsQuery.data?.required_step ? (
                <p className="text-xs text-muted-foreground" data-testid="project-command-panel-required-step">
                  Required step: {projectAllowedActionsQuery.data.required_step}
                </p>
              ) : null}
              {projectAllowedActionsQuery.data?.blocked_reason ? (
                <p className="text-xs text-muted-foreground" data-testid="project-command-panel-blocked-reason">
                  {projectAllowedActionsQuery.data.blocked_reason}
                </p>
              ) : null}
              {lifecycleTransitionConflict ? (
                <p className="text-xs text-destructive" data-testid="project-command-panel-lifecycle-conflict">
                  {lifecycleTransitionConflict}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2" data-testid="project-command-panel-allowed-actions">
                {allowedActions.length === 0 ? (
                  <span className="text-xs text-muted-foreground">No commands currently allowed.</span>
                ) : (
                  allowedActions.map((action) => (
                    <Badge data-testid={`project-command-panel-allowed-action-${action}`} key={action} variant="outline">
                      {action}
                    </Badge>
                  ))
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {isCommandAllowed('ingest') || isCommandAllowed('select_mode') || isCommandAllowed('configure') ? (
                  <Link
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
                    data-testid="project-command-panel-open-setup"
                    to="setup"
                  >
                    Open Setup
                  </Link>
                ) : (
                  <span
                    aria-disabled="true"
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-muted-foreground opacity-60"
                    data-testid="project-command-panel-open-setup-disabled"
                  >
                    Open Setup
                  </span>
                )}
                {isCommandAllowed('run') ? (
                  <Link
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
                    data-testid="project-command-panel-open-runs"
                    to="runs"
                  >
                    Open Runs
                  </Link>
                ) : (
                  <span
                    aria-disabled="true"
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-muted-foreground opacity-60"
                    data-testid="project-command-panel-open-runs-disabled"
                  >
                    Open Runs
                  </span>
                )}
                {isCommandAllowed('export') ? (
                  <Link
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
                    data-testid="project-command-panel-open-exports"
                    to="exports"
                  >
                    Open Exports
                  </Link>
                ) : (
                  <span
                    aria-disabled="true"
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-muted-foreground opacity-60"
                    data-testid="project-command-panel-open-exports-disabled"
                  >
                    Open Exports
                  </span>
                )}
                {isCommandAllowed('configure') ? (
                  <Link
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
                    data-testid="project-command-panel-open-settings"
                    to="settings"
                  >
                    Open Settings
                  </Link>
                ) : (
                  <span
                    aria-disabled="true"
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-muted-foreground opacity-60"
                    data-testid="project-command-panel-open-settings-disabled"
                  >
                    Open Settings
                  </span>
                )}
                {isCommandAllowed('archive') ? (
                  <Button
                    data-testid="project-command-panel-archive-button"
                    disabled={archiveProjectMutation.isMutating}
                    onClick={() => {
                      setIsArchiveConfirmOpen(true);
                    }}
                    size="sm"
                    type="button"
                    variant="destructive"
                  >
                    Archive Project
                  </Button>
                ) : (
                  <span
                    aria-disabled="true"
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-muted-foreground opacity-60"
                    data-testid="project-command-panel-archive-button-disabled"
                  >
                    Archive Project
                  </span>
                )}
                {isCommandAllowed('restore') ? (
                  <Button
                    data-testid="project-command-panel-restore-button"
                    disabled={restoreProjectMutation.isMutating}
                    onClick={() => {
                      setIsRestoreConfirmOpen(true);
                    }}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    Restore Project
                  </Button>
                ) : (
                  <span
                    aria-disabled="true"
                    className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-muted-foreground opacity-60"
                    data-testid="project-command-panel-restore-button-disabled"
                  >
                    Restore Project
                  </span>
                )}
              </div>
              <AlertDialog open={isArchiveConfirmOpen} onOpenChange={setIsArchiveConfirmOpen}>
                <AlertDialogContent data-testid="project-archive-confirm-dialog">
                  <AlertDialogHeader>
                    <AlertDialogTitle>Archive project?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Archiving locks workflow actions until restore. Continue?
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel data-testid="project-archive-confirm-cancel">Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      data-testid="project-archive-confirm-submit"
                      onClick={() => {
                        void handleArchiveProject();
                      }}
                      variant="destructive"
                    >
                      {archiveProjectMutation.isMutating ? 'Archiving...' : 'Confirm archive'}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
              <AlertDialog open={isRestoreConfirmOpen} onOpenChange={setIsRestoreConfirmOpen}>
                <AlertDialogContent data-testid="project-restore-confirm-dialog">
                  <AlertDialogHeader>
                    <AlertDialogTitle>Restore project?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Restore re-enables lifecycle actions based on current project state. Continue?
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel data-testid="project-restore-confirm-cancel">Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      data-testid="project-restore-confirm-submit"
                      onClick={() => {
                        void handleRestoreProject();
                      }}
                    >
                      {restoreProjectMutation.isMutating ? 'Restoring...' : 'Confirm restore'}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          )}
        </div>
        <div className="mt-4 space-y-3 rounded-lg border border-panel-border/70 p-3" data-testid="project-timeline-panel">
          <p className="text-xs font-semibold tracking-wide text-foreground">Activity timeline</p>
          {projectTimelineQuery.isLoading && projectTimelineQuery.data === undefined ? (
            <div data-testid="project-timeline-loading">
              <ApiPanelLoading
                description="Fetching project activity timeline."
                title="Loading timeline"
              />
            </div>
          ) : projectTimelineQuery.error ? (
            <div data-testid="project-timeline-error">
              <ApiPanelError
                description={
                  projectTimelineQuery.error instanceof Error
                    ? projectTimelineQuery.error.message
                    : 'Unable to load timeline events.'
                }
                onRetry={() => {
                  void projectTimelineQuery.mutate();
                }}
                retryLabel="Retry timeline"
                title="Timeline unavailable"
              />
            </div>
          ) : (
            <>
              <p className="text-xs text-muted-foreground" data-testid="project-timeline-pagination-state">
                Page {projectTimelineQuery.data?.page ?? timelinePage} / size {projectTimelineQuery.data?.page_size ?? timelinePageSize} / total{' '}
                {projectTimelineQuery.data?.total_items ?? 0}
              </p>
              <div className="space-y-2">
                {(projectTimelineQuery.data?.items ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground" data-testid="project-timeline-empty">
                    No project activity events yet.
                  </p>
                ) : (
                  projectTimelineQuery.data?.items.map((event) => (
                    <div
                      className="rounded-md border border-panel-border/70 px-3 py-2 text-xs"
                      data-testid={`project-timeline-item-${event.event_id}`}
                      key={event.event_id}
                    >
                      <p className="font-medium text-foreground">
                        {event.event_type} by {event.actor}
                      </p>
                      <p className="text-muted-foreground">
                        {event.created_at}
                        {event.run_id !== null ? ` • run ${event.run_id}` : ''}
                      </p>
                    </div>
                  ))
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  data-testid="project-timeline-prev-page"
                  disabled={timelinePage <= 1}
                  onClick={() => setTimelinePage((currentPage) => Math.max(1, currentPage - 1))}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  Previous
                </Button>
                <Button
                  data-testid="project-timeline-next-page"
                  disabled={!projectTimelineQuery.data?.has_next_page}
                  onClick={() => setTimelinePage((currentPage) => currentPage + 1)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  Next
                </Button>
              </div>
            </>
          )}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
            data-testid="project-workspace-home-open-overview"
            to="overview"
          >
            Open Overview
          </Link>
          <Link
            className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
            data-testid="project-workspace-home-open-setup"
            to="setup"
          >
            Open Setup
          </Link>
          <Link
            className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
            data-testid="project-workspace-home-open-runs"
            to="runs"
          >
            Open Runs
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
