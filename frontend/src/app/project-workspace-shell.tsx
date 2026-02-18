import { useEffect } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useProjectAllowedActionsQuery, useProjectSetupStatusQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

type WorkspaceNavItem = {
  id: 'overview' | 'setup' | 'characters' | 'voice' | 'runs' | 'exports' | 'settings';
  to: string;
  label: string;
  end?: boolean;
};

type WorkspaceNavGroup = {
  id: 'foundation' | 'content' | 'operations';
  label: string;
  items: WorkspaceNavItem[];
};

const PROJECT_WORKSPACE_NAV_GROUPS: WorkspaceNavGroup[] = [
  {
    id: 'foundation',
    label: 'Foundation',
    items: [
      { id: 'overview', to: 'overview', label: 'Overview', end: true },
      { id: 'setup', to: 'setup', label: 'Setup' },
    ],
  },
  {
    id: 'content',
    label: 'Content',
    items: [
      { id: 'characters', to: 'characters', label: 'Characters' },
      { id: 'voice', to: 'voice', label: 'Voice' },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { id: 'runs', to: 'runs', label: 'Runs' },
      { id: 'exports', to: 'exports', label: 'Exports' },
      { id: 'settings', to: 'settings', label: 'Settings' },
    ],
  },
];

const ACTION_GATED_ITEM_IDS_BY_REQUIRED_STEP: Record<string, ReadonlySet<WorkspaceNavItem['id']>> = {
  ingestion: new Set<WorkspaceNavItem['id']>(['characters', 'voice', 'runs', 'exports']),
  mode_selection: new Set<WorkspaceNavItem['id']>(['voice', 'runs', 'exports']),
  initial_run: new Set<WorkspaceNavItem['id']>(['exports']),
  restore: new Set<WorkspaceNavItem['id']>(['characters', 'voice', 'runs', 'exports', 'settings']),
};

type RequiredStepId = 'ingestion' | 'mode_selection' | 'initial_run' | 'restore';
type WorkspaceNavLockState = {
  locked: boolean;
  reason: string | null;
  requiredStep: RequiredStepId | null;
};

function toProjectSetupPath(projectId: number) {
  return `/projects/${projectId}/setup`;
}

function isSetupPath(pathname: string, projectId: number) {
  const setupPath = toProjectSetupPath(projectId);
  return pathname === setupPath || pathname.startsWith(`${setupPath}/`);
}

function resolveStepReady(stepId: string, steps: Array<{ step_id: string; ready: boolean }> | undefined): boolean {
  if (!steps || steps.length === 0) {
    return false;
  }
  const step = steps.find((candidate) => candidate.step_id === stepId);
  return step?.ready === true;
}

function resolveSetupStepLockReason(
  itemId: WorkspaceNavItem['id'],
  steps: Array<{ step_id: string; ready: boolean }> | undefined,
): { reason: string; requiredStep: RequiredStepId } | null {
  const ingestionReady = resolveStepReady('ingestion', steps);
  const modeSelectionReady = resolveStepReady('mode_selection', steps);
  const initialRunReady = resolveStepReady('initial_run', steps);

  if (itemId === 'characters' && !ingestionReady) {
    return { reason: 'Locked: complete ingestion setup first.', requiredStep: 'ingestion' };
  }
  if ((itemId === 'voice' || itemId === 'runs') && !modeSelectionReady) {
    return { reason: 'Locked: complete mode selection setup first.', requiredStep: 'mode_selection' };
  }
  if (itemId === 'exports' && !initialRunReady) {
    return { reason: 'Locked: complete initial run setup first.', requiredStep: 'initial_run' };
  }
  return null;
}

function resolveActionGatingLockReason(
  itemId: WorkspaceNavItem['id'],
  requiredStep: string | null | undefined,
  blockedReason: string | null | undefined,
): { reason: string; requiredStep: RequiredStepId } | null {
  if (!requiredStep || !blockedReason) {
    return null;
  }
  const affectedItemIds = ACTION_GATED_ITEM_IDS_BY_REQUIRED_STEP[requiredStep];
  if (!affectedItemIds || !affectedItemIds.has(itemId)) {
    return null;
  }
  return { reason: blockedReason, requiredStep: requiredStep as RequiredStepId };
}

function resolveWorkspaceNavLockState(
  itemId: WorkspaceNavItem['id'],
  options: {
    setupSteps: Array<{ step_id: string; ready: boolean }> | undefined;
    actionRequiredStep: string | null | undefined;
    actionBlockedReason: string | null | undefined;
  },
): WorkspaceNavLockState {
  const actionGatingLock = resolveActionGatingLockReason(itemId, options.actionRequiredStep, options.actionBlockedReason);
  if (actionGatingLock) {
    return {
      locked: true,
      reason: actionGatingLock.reason,
      requiredStep: actionGatingLock.requiredStep,
    };
  }
  const setupLock = resolveSetupStepLockReason(itemId, options.setupSteps);
  if (setupLock) {
    return {
      locked: true,
      reason: setupLock.reason,
      requiredStep: setupLock.requiredStep,
    };
  }
  return {
    locked: false,
    reason: null,
    requiredStep: null,
  };
}

function resolveCurrentWorkspaceItemId(pathname: string, projectId: number): WorkspaceNavItem['id'] | null {
  const prefix = `/projects/${projectId}`;
  if (!pathname.startsWith(prefix)) {
    return null;
  }
  const remainder = pathname.slice(prefix.length).replace(/^\//, '');
  const firstSegment = remainder.split('/')[0] ?? '';
  if (firstSegment === '' || firstSegment === 'overview') {
    return 'overview';
  }
  if (firstSegment === 'setup') {
    return 'setup';
  }
  if (firstSegment === 'characters') {
    return 'characters';
  }
  if (firstSegment === 'voice' || firstSegment === 'pipeline-setup') {
    return 'voice';
  }
  if (firstSegment === 'runs' || firstSegment === 'run-monitor') {
    return 'runs';
  }
  if (firstSegment === 'exports' || firstSegment === 'export') {
    return 'exports';
  }
  if (firstSegment === 'settings') {
    return 'settings';
  }
  return null;
}

function resolveRequiredStepRoute(projectId: number, requiredStep: RequiredStepId | null): string {
  if (requiredStep === 'initial_run') {
    return `/projects/${projectId}/runs`;
  }
  if (requiredStep === 'restore') {
    return `/projects/${projectId}/overview`;
  }
  return `/projects/${projectId}/setup`;
}

export function ProjectWorkspaceShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const projectId = parseProjectIdParam(params.project_id);
  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const projectActionsQuery = useProjectAllowedActionsQuery(projectId);
  const currentWorkspaceItemId =
    projectId !== null ? resolveCurrentWorkspaceItemId(location.pathname, projectId) : null;
  const currentRouteLockState =
    currentWorkspaceItemId !== null
      ? resolveWorkspaceNavLockState(currentWorkspaceItemId, {
          setupSteps: setupStatusQuery.data?.steps,
          actionRequiredStep: projectActionsQuery.data?.required_step,
          actionBlockedReason: projectActionsQuery.data?.blocked_reason,
        })
      : null;

  useEffect(() => {
    if (projectId === null || setupStatusQuery.error || setupStatusQuery.isLoading || setupStatusQuery.data === undefined) {
      return;
    }
    if (setupStatusQuery.data.is_complete || isSetupPath(location.pathname, projectId)) {
      return;
    }
    navigate(toProjectSetupPath(projectId), { replace: true });
  }, [
    location.pathname,
    navigate,
    projectId,
    setupStatusQuery.data,
    setupStatusQuery.error,
    setupStatusQuery.isLoading,
  ]);

  return (
    <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]" data-testid="project-workspace-shell">
      <aside className="h-fit rounded-xl border border-panel-border/70 bg-card/55 p-3" data-testid="project-workspace-sidebar">
        <p className="text-[11px] font-semibold tracking-[0.15em] text-muted-foreground uppercase">Project Workspace</p>
        <p className="mt-2 text-sm font-semibold text-foreground" data-testid="project-workspace-shell-project-id">
          Project #{projectId ?? 'n/a'}
        </p>

        <nav aria-label="Project Workspace Navigation" className="mt-3 space-y-4">
          {PROJECT_WORKSPACE_NAV_GROUPS.map((group) => (
            <div data-testid={`project-workspace-nav-group-${group.id}`} key={group.id}>
              <p className="mb-1 px-1 text-[10px] font-semibold tracking-[0.13em] text-muted-foreground uppercase">
                {group.label}
              </p>
              <ul className="space-y-1.5">
                {group.items.map((item) => (
                  <li key={item.id}>
                    {(() => {
                      const lockState = resolveWorkspaceNavLockState(item.id, {
                        setupSteps: setupStatusQuery.data?.steps,
                        actionRequiredStep: projectActionsQuery.data?.required_step,
                        actionBlockedReason: projectActionsQuery.data?.blocked_reason,
                      });
                      return (
                    <NavLink
                      className={({ isActive }) =>
                        [
                          'flex rounded-lg px-2.5 py-2 text-sm transition',
                          isActive ? 'bg-sidebar-active/12 text-sidebar-active' : 'text-sidebar-foreground hover:bg-background/75',
                          lockState.locked ? 'opacity-55' : '',
                        ].join(' ')
                      }
                      aria-disabled={lockState.locked}
                      data-testid={`project-workspace-nav-${item.id}`}
                      end={item.end}
                      onClick={(event) => {
                        if (!lockState.locked) {
                          return;
                        }
                        event.preventDefault();
                      }}
                      title={lockState.reason ?? undefined}
                      to={item.to}
                    >
                      {item.label}
                    </NavLink>
                      );
                    })()}
                    {(() => {
                      const lockState = resolveWorkspaceNavLockState(item.id, {
                        setupSteps: setupStatusQuery.data?.steps,
                        actionRequiredStep: projectActionsQuery.data?.required_step,
                        actionBlockedReason: projectActionsQuery.data?.blocked_reason,
                      });
                      if (!lockState.reason) {
                        return null;
                      }
                      return (
                        <p
                          className="mt-1 px-2 text-[11px] text-muted-foreground"
                          data-testid={`project-workspace-nav-locked-reason-${item.id}`}
                        >
                          {lockState.reason}
                        </p>
                      );
                    })()}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      <section className="min-w-0">
        {projectId !== null && currentRouteLockState?.locked && !isSetupPath(location.pathname, projectId) ? (
          <Card data-testid="project-workspace-deep-link-guard">
            <CardHeader>
              <CardTitle>Route locked</CardTitle>
              <CardDescription>
                {currentRouteLockState.reason ?? 'This route is currently locked for this project.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                data-testid="project-workspace-deep-link-guard-action"
                onClick={() => {
                  navigate(resolveRequiredStepRoute(projectId, currentRouteLockState.requiredStep));
                }}
              >
                Go to required step
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Outlet />
        )}
      </section>
    </div>
  );
}
