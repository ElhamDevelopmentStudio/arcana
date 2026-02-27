import { NavLink } from 'react-router-dom';
import {
  Analytics01Icon,
  BookOpen01Icon,
  CheckListIcon,
  CpuIcon,
  DashboardSquare02Icon,
  Download02Icon,
  PlayCircleIcon,
  UserSearch01Icon,
} from 'hugeicons-react';
import type { ComponentType } from 'react';

type ProjectStepNavProps = {
  projectId: string | null;
  collapsed?: boolean;
};

type StepConfig = {
  path: string;
  label: string;
  icon: ComponentType<{ className?: string; size?: number; strokeWidth?: number }>;
};

const PROJECT_STEPS: StepConfig[] = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    icon: DashboardSquare02Icon,
  },
  {
    path: '/projects/new',
    label: 'Create Project',
    icon: BookOpen01Icon,
  },
  {
    path: '/projects/:project_id/mode',
    label: 'Mode Selection',
    icon: CheckListIcon,
  },
  {
    path: '/projects/:project_id/characters',
    label: 'Character Map',
    icon: UserSearch01Icon,
  },
  {
    path: '/projects/:project_id/pipeline-setup',
    label: 'Pipeline Setup',
    icon: CpuIcon,
  },
  {
    path: '/projects/:project_id/run-monitor',
    label: 'Run Monitor',
    icon: PlayCircleIcon,
  },
  {
    path: '/projects/:project_id/export',
    label: 'Export',
    icon: Download02Icon,
  },
  {
    path: '/projects/:project_id/dashboards',
    label: 'Dashboards',
    icon: Analytics01Icon,
  },
];

function resolvePath(path: string, projectId: string | null): string {
  if (!path.includes(':project_id')) {
    return path;
  }
  return path.replace(':project_id', projectId ?? 'missing');
}

function isProjectStepLocked(path: string, projectId: string | null): boolean {
  if (!path.includes(':project_id')) {
    return false;
  }
  return projectId === null;
}

export function ProjectStepNav({ projectId, collapsed = false }: ProjectStepNavProps) {
  return (
    <nav aria-label="Workflow" className="space-y-2">
      {!collapsed ? (
        <p className="px-2 text-[11px] font-semibold tracking-[0.15em] text-muted-foreground uppercase">Pipeline Steps</p>
      ) : null}

      <ul className="grid gap-1.5">
        {PROJECT_STEPS.map((step, index) => {
          const locked = isProjectStepLocked(step.path, projectId);
          const to = resolvePath(step.path, projectId);
          const Icon = step.icon;

          return (
            <li key={step.path}>
              <NavLink
                className={({ isActive }) =>
                  [
                    'group flex items-center text-sm transition',
                    collapsed ? 'mx-auto h-12 w-12 justify-center rounded-2xl' : 'rounded-xl gap-2.5 px-3 py-2.5',
                    isActive
                      ? 'bg-sidebar-active/12 text-sidebar-active'
                      : 'text-sidebar-foreground hover:bg-background/75',
                    locked ? 'pointer-events-none opacity-45' : '',
                  ].join(' ')
                }
                title={collapsed ? step.label : undefined}
                to={to}
              >
                <span className={collapsed ? 'grid size-5 place-items-center text-muted-foreground' : 'grid size-6 place-items-center rounded-lg bg-secondary/65 text-muted-foreground'}>
                  <Icon size={16} strokeWidth={1.9} />
                </span>
                {!collapsed ? (
                  <>
                    <span className="line-clamp-1 flex-1 font-medium tracking-[-0.01em]">{step.label}</span>
                    <span className="text-[11px] font-semibold text-muted-foreground">{String(index + 1).padStart(2, '0')}</span>
                  </>
                ) : null}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
