import { NavLink } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';

type ProjectStepNavProps = {
  projectId: string | null;
};

type StepConfig = {
  path: string;
  label: string;
  short: string;
};

const PROJECT_STEPS: StepConfig[] = [
  {
    path: '/projects/new',
    label: 'Create Project',
    short: '01',
  },
  {
    path: '/projects/:project_id/mode',
    label: 'Mode Selection',
    short: '02',
  },
  {
    path: '/projects/:project_id/characters',
    label: 'Character Map',
    short: '03',
  },
  {
    path: '/projects/:project_id/pipeline-setup',
    label: 'Pipeline Setup',
    short: '04',
  },
  {
    path: '/projects/:project_id/run-monitor',
    label: 'Run Monitor',
    short: '05',
  },
  {
    path: '/projects/:project_id/export',
    label: 'Export',
    short: '06',
  },
  {
    path: '/projects/:project_id/dashboards',
    label: 'Dashboards',
    short: '07',
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

export function ProjectStepNav({ projectId }: ProjectStepNavProps) {
  return (
    <nav aria-label="Workflow" className="nipe-panel p-3.5">
      <p className="px-1 text-[11px] font-semibold tracking-[0.15em] text-muted-foreground uppercase">Pipeline Steps</p>
      <ul className="mt-2 grid gap-1.5">
        {PROJECT_STEPS.map((step) => {
          const locked = isProjectStepLocked(step.path, projectId);
          const to = resolvePath(step.path, projectId);

          return (
            <li key={step.path}>
              <NavLink
                className={({ isActive }) =>
                  [
                    'group flex h-full items-center gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition',
                    isActive
                      ? 'border-sidebar-active/30 bg-sidebar-active/10 text-sidebar-active shadow-[0_8px_18px_-14px_hsl(var(--primary)/0.8)]'
                      : 'border-transparent text-sidebar-foreground hover:border-border hover:bg-background/85',
                    locked ? 'pointer-events-none opacity-45' : '',
                  ].join(' ')
                }
                to={to}
              >
                <Badge variant={locked ? 'outline' : 'secondary'} className="font-mono text-[10px]">
                  {step.short}
                </Badge>
                <span className="line-clamp-1 font-medium tracking-[-0.01em]">{step.label}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
