import { Link } from 'react-router-dom';

export function ProjectWorkspaceHomePage() {
  return (
    <div className="rounded-xl border border-panel-border/70 bg-card/55 p-5" data-testid="project-workspace-home">
      <h2 className="text-lg font-semibold text-foreground">Project workspace</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        This workspace is project-scoped. Use the sidebar to open setup and project workflow modules.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75" to="mode">
          Open Mode
        </Link>
        <Link
          className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75"
          to="pipeline-setup"
        >
          Open Pipeline Setup
        </Link>
        <Link className="rounded-md border border-panel-border/70 px-3 py-1.5 text-sm text-foreground hover:bg-background/75" to="run-monitor">
          Open Run Monitor
        </Link>
      </div>
    </div>
  );
}
