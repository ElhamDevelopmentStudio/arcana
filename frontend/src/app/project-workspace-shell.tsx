import { useEffect } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';

import { useProjectSetupStatusQuery } from '@/features/workflow/api/workflow-hooks';
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

function toProjectSetupPath(projectId: number) {
  return `/projects/${projectId}/setup`;
}

function isSetupPath(pathname: string, projectId: number) {
  const setupPath = toProjectSetupPath(projectId);
  return pathname === setupPath || pathname.startsWith(`${setupPath}/`);
}

export function ProjectWorkspaceShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const projectId = parseProjectIdParam(params.project_id);
  const setupStatusQuery = useProjectSetupStatusQuery(projectId);

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
                    <NavLink
                      className={({ isActive }) =>
                        [
                          'flex rounded-lg px-2.5 py-2 text-sm transition',
                          isActive ? 'bg-sidebar-active/12 text-sidebar-active' : 'text-sidebar-foreground hover:bg-background/75',
                        ].join(' ')
                      }
                      data-testid={`project-workspace-nav-${item.id}`}
                      end={item.end}
                      to={item.to}
                    >
                      {item.label}
                    </NavLink>
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
