import { useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  LayoutDashboard,
  Upload,
  Sliders,
  Users,
  Mic2,
  Volume2,
  Settings2,
  Play,
  Download,
  BarChart2,
  Settings,
  Lock,
} from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/utils';
import { useProjectAllowedActionsQuery, useProjectSetupStatusQuery, useProjectDetailQuery } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

type WorkspaceNavItem = {
  id: 'overview' | 'upload' | 'mode' | 'characters' | 'voice' | 'pronunciation' | 'pipeline' | 'runs' | 'exports' | 'analytics' | 'settings';
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  end?: boolean;
};

type WorkspaceNavGroup = {
  id: string;
  label: string;
  items: WorkspaceNavItem[];
};

const buildNavGroups = (projectId: number): WorkspaceNavGroup[] => [
  {
    id: 'setup',
    label: 'Setup',
    items: [
      { id: 'overview', to: `/projects/${projectId}/overview`, label: 'Overview', icon: LayoutDashboard, end: true },
      { id: 'upload', to: `/projects/${projectId}/setup`, label: 'Upload', icon: Upload },
    ],
  },
  {
    id: 'configuration',
    label: 'Configuration',
    items: [
      { id: 'mode', to: `/projects/${projectId}/mode`, label: 'Mode', icon: Sliders },
      { id: 'characters', to: `/projects/${projectId}/characters`, label: 'Characters', icon: Users },
      { id: 'pronunciation', to: `/projects/${projectId}/pronunciation`, label: 'Pronunciation', icon: Volume2 },
      { id: 'voice', to: `/projects/${projectId}/voice`, label: 'Voice', icon: Mic2 },
      { id: 'pipeline', to: `/projects/${projectId}/pipeline-setup`, label: 'Pipeline', icon: Settings2 },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { id: 'runs', to: `/projects/${projectId}/runs`, label: 'Runs', icon: Play },
      { id: 'exports', to: `/projects/${projectId}/exports`, label: 'Exports', icon: Download },
    ],
  },
  {
    id: 'insights',
    label: 'Insights',
    items: [
      { id: 'analytics', to: `/projects/${projectId}/dashboards`, label: 'Analytics', icon: BarChart2 },
    ],
  },
  {
    id: 'manage',
    label: 'Manage',
    items: [
      { id: 'settings', to: `/projects/${projectId}/settings`, label: 'Settings', icon: Settings },
    ],
  },
];

const LOCK_RULES: Record<WorkspaceNavItem['id'], Array<'ingestion' | 'mode_selection' | 'initial_run'>> = {
  overview: [],
  upload: [],
  mode: [],
  characters: ['ingestion'],
  pronunciation: ['ingestion'],
  voice: ['ingestion', 'mode_selection'],
  pipeline: ['ingestion', 'mode_selection'],
  runs: ['ingestion', 'mode_selection'],
  exports: ['ingestion', 'mode_selection', 'initial_run'],
  analytics: ['initial_run'],
  settings: [],
};

const LOCK_MESSAGES: Record<string, string> = {
  ingestion: 'Complete source upload first',
  mode_selection: 'Select a mode first',
  initial_run: 'Complete an initial run first',
};

function resolveIsLocked(
  itemId: WorkspaceNavItem['id'],
  setupSteps: Array<{ step_id: string; ready: boolean }> | undefined,
  actionRequiredStep: string | null | undefined,
  actionBlockedReason: string | null | undefined,
): { locked: boolean; message: string | null } {
  const rules = LOCK_RULES[itemId] ?? [];
  for (const rule of rules) {
    const step = setupSteps?.find((s) => s.step_id === rule);
    if (step && !step.ready) {
      return { locked: true, message: LOCK_MESSAGES[rule] ?? 'This step is locked' };
    }
  }
  if (actionRequiredStep && actionBlockedReason) {
    const affectedByAction = ['characters', 'voice', 'runs', 'exports'];
    if (affectedByAction.includes(itemId)) {
      const affectedSet = new Set(
        actionRequiredStep === 'ingestion' ? ['characters', 'voice', 'runs', 'exports'] :
        actionRequiredStep === 'mode_selection' ? ['voice', 'runs', 'exports'] :
        actionRequiredStep === 'initial_run' ? ['exports'] : []
      );
      if (affectedSet.has(itemId)) {
        return { locked: true, message: actionBlockedReason };
      }
    }
  }
  return { locked: false, message: null };
}

export function ProjectWorkspaceShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const projectId = parseProjectIdParam(params.project_id);
  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const projectActionsQuery = useProjectAllowedActionsQuery(projectId);
  const projectQuery = useProjectDetailQuery(projectId);
  const projectTitle = projectQuery.data?.title ?? (projectId !== null ? `Project #${projectId}` : 'Project');

  useEffect(() => {
    if (projectId === null || setupStatusQuery.error || setupStatusQuery.isLoading || setupStatusQuery.data === undefined) return;
    const setupPath = `/projects/${projectId}/setup`;
    const modePath = `/projects/${projectId}/mode`;
    const overviewPath = `/projects/${projectId}/overview`;
    const steps = setupStatusQuery.data.steps ?? [];
    const ingestionReady = steps.find((s) => s.step_id === 'ingestion')?.ready ?? false;
    const isOnSetupOrMode = location.pathname === setupPath || location.pathname.startsWith(`${setupPath}/`) ||
      location.pathname === modePath || location.pathname === overviewPath;
    // Only force-redirect to /setup if ingestion itself hasn't been done yet.
    // Pages that need mode_selection or initial_run show their own locked states via the sidebar.
    if (!ingestionReady && !isOnSetupOrMode) {
      navigate(setupPath, { replace: true });
    }
  }, [location.pathname, navigate, projectId, setupStatusQuery.data, setupStatusQuery.error, setupStatusQuery.isLoading]);

  if (projectId === null) {
    return (
      <div className="flex h-full flex-col overflow-auto p-8">
        <p className="text-sm text-muted-foreground">Invalid project ID.</p>
      </div>
    );
  }

  const navGroups = buildNavGroups(projectId);

  return (
    <div className="flex h-full min-w-0" data-testid="project-workspace-shell">
      {/* Project sidebar */}
      <aside
        aria-label="Project navigation"
        className="flex w-56 shrink-0 flex-col border-r border-white/10 bg-sidebar overflow-y-auto"
        data-testid="project-workspace-sidebar"
      >
        {/* Back to projects */}
        <div className="shrink-0 border-b border-white/10 p-3">
          <Link
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
            to="/dashboard"
          >
            <ArrowLeft size={13} />
            All Projects
          </Link>
          <p
            className="mt-2 truncate px-2 text-sm font-semibold text-foreground"
            data-testid="project-workspace-shell-project-id"
          >
            {projectTitle}
          </p>
        </div>

        {/* Nav groups */}
        <nav aria-label="Project Workspace Navigation" className="flex-1 overflow-y-auto p-2">
          {navGroups.map((group) => (
            <div className="mb-3" data-testid={`project-workspace-nav-group-${group.id}`} key={group.id}>
              <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50">
                {group.label}
              </p>
              <ul className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const lockState = resolveIsLocked(
                    item.id,
                    setupStatusQuery.data?.steps,
                    projectActionsQuery.data?.required_step,
                    projectActionsQuery.data?.blocked_reason,
                  );
                  return (
                    <li key={item.id}>
                      <NavLink
                        aria-disabled={lockState.locked}
                        className={({ isActive }) =>
                          cn(
                            'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors duration-100',
                            isActive
                              ? 'bg-sidebar-accent text-foreground'
                              : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
                            lockState.locked && 'pointer-events-none opacity-40',
                          )
                        }
                        data-testid={`project-workspace-nav-${item.id}`}
                        end={item.end}
                        onClick={(e) => {
                          if (lockState.locked) {
                            e.preventDefault();
                            toast.info(lockState.message ?? 'This step is locked');
                          }
                        }}
                        to={item.to}
                      >
                        <Icon className="shrink-0" size={14} />
                        <span>{item.label}</span>
                        {lockState.locked && <Lock className="ml-auto shrink-0 text-muted-foreground/40" size={12} />}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      {/* Page content */}
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Outlet />
      </section>
    </div>
  );
}
