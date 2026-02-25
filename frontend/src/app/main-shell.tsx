import { Outlet, useLocation, useParams } from 'react-router-dom';

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

export function MainShell() {
  const location = useLocation();
  const params = useParams<{ project_id?: string }>();
  const projectId = getProjectIdFromPath(location.pathname, params.project_id);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-[1320px] flex-col gap-5 px-4 py-6 lg:px-8">
        <header className="rounded-2xl border bg-card px-6 py-5 shadow-sm">
          <p className="text-xs font-semibold tracking-[0.18em] text-primary uppercase">NIPE Workflow</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight lg:text-4xl">Narrative Pipeline Workspace</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Each screen covers one step only. Move through project creation, mode selection, character prep, pipeline setup, and exports in sequence.
          </p>
        </header>

        <ProjectStepNav projectId={projectId} />

        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
