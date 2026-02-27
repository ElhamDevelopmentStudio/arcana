import { useParams } from 'react-router-dom';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectSettingsPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  return (
    <WorkflowPageShell
      description="Project-scoped settings and policy controls."
      step="Settings"
      title="Project Settings"
    >
      <Card data-testid="project-settings-placeholder">
        <CardHeader>
          <CardTitle>Settings module</CardTitle>
          <CardDescription>
            Settings route is reserved for project-level policy controls and advanced preferences.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>Project: {projectId ?? 'n/a'}</p>
          <Badge variant="outline">Placeholder route</Badge>
          <p>
            Backend settings endpoints beyond current workflow are not yet integrated in this view.
          </p>
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
