import { useEffect } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';

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
  restore: new Set<WorkspaceNavItem['id']>([]),
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
): string | null {
  const ingestionReady = resolveStepReady('ingestion', steps);
  const modeSelectionReady = resolveStepReady('mode_selection', steps);
  const initialRunReady = resolveStepReady('initial_run', steps);

  if (itemId === 'characters' && !ingestionReady) {
    return 'Locked: complete ingestion setup first.';
  }
  if ((itemId === 'voice' || itemId === 'runs') && !modeSelectionReady) {
    return 'Locked: complete mode selection setup first.';
  }
  if (itemId === 'exports' && !initialRunReady) {
    return 'Locked: complete initial run setup first.';
  }
  return null;
}

function resolveActionGatingLockReason(
  itemId: WorkspaceNavItem['id'],
  requiredStep: string | null | undefined,
  blockedReason: string | null | undefined,
): string | null {
  if (!requiredStep || !blockedReason) {
    return null;
  }
  const affectedItemIds = ACTION_GATED_ITEM_IDS_BY_REQUIRED_STEP[requiredStep];
  if (!affectedItemIds || !affectedItemIds.has(itemId)) {
    return null;
  }
  return blockedReason;
}

export function ProjectWorkspaceShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const projectId = parseProjectIdParam(params.project_id);
  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const projectActionsQuery = useProjectAllowedActionsQuery(projectId);

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
                      const setupStepLockReason = resolveSetupStepLockReason(item.id, setupStatusQuery.data?.steps);
                      const actionGatingLockReason = resolveActionGatingLockReason(
                        item.id,
                        projectActionsQuery.data?.required_step,
                        projectActionsQuery.data?.blocked_reason,
                      );
                      const lockReason = actionGatingLockReason ?? setupStepLockReason;
                      const locked = lockReason !== null;
                      return (
                    <NavLink
                      className={({ isActive }) =>
                        [
                          'flex rounded-lg px-2.5 py-2 text-sm transition',
                          isActive ? 'bg-sidebar-active/12 text-sidebar-active' : 'text-sidebar-foreground hover:bg-background/75',
                          locked ? 'opacity-55' : '',
                        ].join(' ')
                      }
                      aria-disabled={locked}
                      data-testid={`project-workspace-nav-${item.id}`}
                      end={item.end}
                      onClick={(event) => {
                        if (!locked) {
                          return;
                        }
                        event.preventDefault();
                      }}
                      title={lockReason ?? undefined}
                      to={item.to}
                    >
                      {item.label}
                    </NavLink>
                      );
                    })()}
                    {(() => {
                      const setupStepLockReason = resolveSetupStepLockReason(item.id, setupStatusQuery.data?.steps);
                      const actionGatingLockReason = resolveActionGatingLockReason(
                        item.id,
                        projectActionsQuery.data?.required_step,
                        projectActionsQuery.data?.blocked_reason,
                      );
                      const lockReason = actionGatingLockReason ?? setupStepLockReason;
                      if (!lockReason) {
                        return null;
                      }
                      return (
                        <p
                          className="mt-1 px-2 text-[11px] text-muted-foreground"
                          data-testid={`project-workspace-nav-locked-reason-${item.id}`}
                        >
                          {lockReason}
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
        <Outlet />
      </section>
    </div>
  );
}
