import { useNavigate, useParams } from 'react-router-dom';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';

export function ProjectLowConfidenceReviewGuidePage() {
  const params = useParams<{ project_id: string }>();
  const navigate = useNavigate();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);

  const projectId = routeProjectId ?? storeProjectId;

  return (
    <WorkflowPageShell
      step="Reference"
      title="How to review low-confidence outputs"
      description="A focused guide for validating low-confidence tags before export."
      action={
        projectId === null ? (
          <span className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground">Project required</span>
        ) : (
          <Button variant="outline" onClick={() => navigate(projectRoute(projectId, 'review/low-confidence'))}>
            Open low-confidence review queue
          </Button>
        )
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Goal of the queue</CardTitle>
          <CardDescription>
            Review low-confidence tags before export so final audiobook artifacts are deterministic, explainable, and cleaner.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>
            The low-confidence queue surfaces regions where model confidence is below the configured validation threshold.
            You should review every highlighted row before locking the final export.
          </p>
          <ol className="list-inside list-decimal space-y-2 pl-1">
            <li>Open the <strong>low-confidence review queue</strong> from the run monitor.</li>
            <li>Use the segment-level preview to confirm if the confidence score is contextually correct.</li>
            <li>
              For each row, validate speaker and tag assignment. If correct, mark it as accepted; if uncertain, force a manual
              correction.
            </li>
            <li>Use <strong>next/previous</strong> controls to keep momentum and avoid missing any candidate.</li>
            <li>After completing the queue, return to <strong>Export</strong> and confirm export readiness indicators.</li>
          </ol>
          <p>
            Recommended pattern: prioritize rows tied to recurring names and emotionally dense scenes first; these typically
            improve downstream narration consistency the most.
          </p>
          <p data-testid="low-confidence-guide-tip">
            If confidence remains consistently low on a speaker, consider revisiting character map finalization or adding a
            custom voice rule before rerun.
          </p>
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
