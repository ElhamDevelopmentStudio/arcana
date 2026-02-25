import { Outlet, useLocation, useParams } from 'react-router-dom';
import { Bell, CircleHelp, ContactRound, Search, Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { ProjectStepNav } from '@/app/project-step-nav';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

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
  const location = useLocation();
  const params = useParams<{ project_id?: string }>();
  const projectId = getProjectIdFromPath(location.pathname, params.project_id);
  const routeMeta = resolveRouteMeta(location.pathname);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto w-full max-w-[1680px] px-4 py-6 lg:px-6">
        <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
          <aside className="nipe-sidebar p-4 lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]">
            <div className="flex h-full flex-col gap-4">
              <div className="rounded-2xl bg-linear-to-br from-primary via-primary to-chart-2 p-4 text-primary-foreground shadow-[0_18px_30px_-24px_hsl(var(--primary)/0.9)]">
                <p className="text-[11px] font-semibold tracking-[0.18em] uppercase text-primary-foreground/85">NIPE Console</p>
                <h1 className="mt-2 text-[1.35rem] font-bold tracking-tight">Narrative Intelligence</h1>
                <p className="mt-2 text-sm text-primary-foreground/90">Elegant orchestration for long-form story pipelines.</p>
              </div>

              <ProjectStepNav projectId={projectId} />

              <div className="nipe-panel mt-auto space-y-3 p-4">
                <p className="text-[11px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">Support</p>
                <button className="flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left text-sm text-sidebar-foreground transition hover:bg-secondary/70" type="button">
                  <CircleHelp className="size-4 text-muted-foreground" />
                  Help Center
                </button>
                <button className="flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left text-sm text-sidebar-foreground transition hover:bg-secondary/70" type="button">
                  <ContactRound className="size-4 text-muted-foreground" />
                  Contact Support
                </button>
              </div>
            </div>
          </aside>

          <div className="space-y-4">
            <header className="nipe-topbar px-5 py-4 lg:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="relative min-w-[240px] flex-1 lg:max-w-lg">
                  <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input className="h-11 pl-10" placeholder="Search workflow, run IDs, or project notes..." />
                </div>
                <div className="flex items-center gap-2">
                  <Button size="icon-sm" variant="outline">
                    <Bell className="size-4" />
                  </Button>
                  <Badge variant="secondary">Project #{projectId ?? '—'}</Badge>
                </div>
              </div>
            </header>

            <header className="nipe-topbar px-5 py-4 lg:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold tracking-[0.17em] text-muted-foreground uppercase">Workflow Context</p>
                  <h2 className="mt-1 text-2xl font-bold tracking-tight text-panel-foreground lg:text-[2rem]">{routeMeta.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{routeMeta.description}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">Structured Flow</Badge>
                  <Badge variant="outline">One Page, One Goal</Badge>
                  <Badge variant="secondary" className="gap-1">
                    <Sparkles className="size-3.5" />
                    Design Refresh
                  </Badge>
                </div>
              </div>
            </header>

            <main>
              <Outlet />
            </main>
          </div>
        </div>
      </div>
    </div>
  );
}
