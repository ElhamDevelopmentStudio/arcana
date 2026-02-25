import { useState } from 'react';
import { Outlet, useLocation, useParams } from 'react-router-dom';
import { DashboardSquare02Icon, PanelLeftCloseIcon, PanelLeftOpenIcon, Search01Icon } from 'hugeicons-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { ProjectStepNav } from '@/app/project-step-nav';

function getProjectIdFromPath(pathname: string, fallback: string | undefined): string | null {
  if (fallback) {
    return fallback;
  }
  const match = pathname.match(/\/projects\/([^/]+)/);
  if (!match || match[1] === 'new') {
    return null;
  }
  return match[1];
}

const ROUTE_META: Array<{ pattern: RegExp; title: string; description: string }> = [
  {
    pattern: /\/projects\/new$/,
    title: 'Project Onboarding',
    description: 'Start by creating a project and ingesting source text.',
  },
  {
    pattern: /\/projects\/[^/]+\/mode$/,
    title: 'Mode Calibration',
    description: 'Set the narrative processing mode before downstream steps.',
  },
  {
    pattern: /\/projects\/[^/]+\/characters$/,
    title: 'Character Intelligence',
    description: 'Shape voice-ready identity data through import and manual curation.',
  },
  {
    pattern: /\/projects\/[^/]+\/pipeline-setup$/,
    title: 'Pipeline Control',
    description: 'Tune runtime behavior and trigger deterministic generation runs.',
  },
  {
    pattern: /\/projects\/[^/]+\/run-monitor$/,
    title: 'Run Observability',
    description: 'Track run status, segment counts, and operational details.',
  },
  {
    pattern: /\/projects\/[^/]+\/export$/,
    title: 'Export Delivery',
    description: 'Review readiness and package outputs for downstream consumers.',
  },
  {
    pattern: /\/projects\/[^/]+\/dashboards$/,
    title: 'Narrative Analytics',
    description: 'Inspect tension, valence, and dominance trends across the corpus.',
  },
];

function resolveRouteMeta(pathname: string) {
  const matched = ROUTE_META.find((item) => item.pattern.test(pathname));
  if (matched) {
    return matched;
  }
  return {
    title: 'Narrative Pipeline Workspace',
    description: 'Move through each workflow step in sequence.',
  };
}

export function MainShell() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const location = useLocation();
  const params = useParams<{ project_id?: string }>();
  const projectId = getProjectIdFromPath(location.pathname, params.project_id);
  const routeMeta = resolveRouteMeta(location.pathname);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="h-screen w-full">
        <div
          className="nipe-shell-frame grid h-full min-h-0 overflow-hidden rounded-none border-0 shadow-none"
          style={{
            gridTemplateColumns: isSidebarCollapsed ? '112px minmax(0, 1fr)' : '296px minmax(0, 1fr)',
            gridTemplateRows: '112px minmax(0, 1fr)',
          }}
        >
          <div className="nipe-sidebar border-r border-b border-panel-border/70">
            {isSidebarCollapsed ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 px-2 py-3">
                <span className="nipe-logo-chip">
                  <DashboardSquare02Icon size={18} strokeWidth={1.9} />
                </span>
                <Button
                  aria-label="Expand sidebar"
                  className="size-9 rounded-2xl border border-panel-border/80 bg-background/70"
                  size="icon"
                  variant="ghost"
                  onClick={() => setIsSidebarCollapsed(false)}
                >
                  <PanelLeftOpenIcon size={16} />
                </Button>
              </div>
            ) : (
              <div className="flex h-full items-center justify-between gap-3 px-5 py-4">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="nipe-logo-chip">
                    <DashboardSquare02Icon size={18} strokeWidth={1.9} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold tracking-[0.16em] text-muted-foreground uppercase">NIPE</p>
                    <h1 className="truncate text-lg font-bold tracking-tight">Narrative Pipeline</h1>
                  </div>
                </div>
                <Button
                  aria-label="Collapse sidebar"
                  className="size-8 rounded-xl"
                  size="icon"
                  variant="ghost"
                  onClick={() => setIsSidebarCollapsed(true)}
                >
                  <PanelLeftCloseIcon size={16} />
                </Button>
              </div>
            )}
          </div>

          <header className="nipe-min-header">
            <div className="min-w-0 text-sm">
              <span className="text-muted-foreground">Projects</span>
              <span className="px-2 text-muted-foreground/70">/</span>
              <span className="font-semibold text-foreground">{routeMeta.title}</span>
            </div>

            <div className="nipe-search-shell">
              <Search01Icon size={17} className="text-muted-foreground" />
              <Input
                aria-label="Search"
                className="h-9 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
                placeholder="Search"
              />
              <kbd className="rounded-md border border-panel-border bg-background px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
                ⌘K
              </kbd>
            </div>
          </header>

          <aside className={cn('nipe-sidebar flex min-h-0 flex-col border-r border-panel-border/70', isSidebarCollapsed ? 'w-[112px]' : 'w-[296px]')}>
            <div className="flex-1 overflow-auto p-3">
              <ProjectStepNav collapsed={isSidebarCollapsed} projectId={projectId} />
            </div>

            {!isSidebarCollapsed ? (
              <div className="border-t border-panel-border/70 px-4 py-3">
                <p className="text-xs text-muted-foreground">Current flow</p>
                <p className="mt-1 text-sm font-medium text-foreground">{routeMeta.title}</p>
              </div>
            ) : null}
          </aside>

          <main className="min-h-0 overflow-auto p-5 lg:p-7">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
