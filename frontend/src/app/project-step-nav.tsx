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
    <nav aria-label="Workflow" className="rounded-xl border bg-card p-3 shadow-sm">
      <ul className="grid gap-2 lg:grid-cols-7">
        {PROJECT_STEPS.map((step) => {
          const locked = isProjectStepLocked(step.path, projectId);
          const to = resolvePath(step.path, projectId);

          return (
            <li key={step.path}>
              <NavLink
                className={({ isActive }) =>
                  [
                    'group flex h-full items-center gap-2 rounded-lg border px-3 py-2 text-sm transition',
                    isActive ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-background hover:bg-accent/40',
                    locked ? 'pointer-events-none opacity-40' : '',
                  ].join(' ')
                }
                to={to}
              >
                <Badge variant="outline" className="font-mono text-[10px]">
                  {step.short}
                </Badge>
                <span className="line-clamp-1">{step.label}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
