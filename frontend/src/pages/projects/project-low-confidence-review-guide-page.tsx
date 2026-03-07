import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useParams } from 'react-router-dom';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { useWorkspaceStore } from '@/app/state/workspace-store';

const GUIDE_STEPS = [
  {
    step: '01',
    title: 'Understand the flags',
    body: 'Low-confidence flags appear when the model assigns a speaker or emotion with less than 80% certainty. These segments should be manually validated.',
  },
  {
    step: '02',
    title: 'Check surrounding context',
    body: 'Read 2–3 segments before and after the flagged segment. Often the speaker is established in a nearby dialogue tag.',
  },
  {
    step: '03',
    title: 'Accept or override',
    body: 'If the model assignment is correct, accept it. If not, note corrections for re-tagging or adjust manually via the speaker review interface.',
  },
  {
    step: '04',
    title: 'Prioritize by chapter',
    body: 'Work through chapters sequentially to maintain context continuity. Reviewing out of order may cause inconsistent overrides.',
  },
];

export function ProjectLowConfidenceReviewGuidePage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Review Guide`}
      title="Low-Confidence Review Guide"
      description="How to efficiently validate uncertain tagging output before export."
    >
      <div className="max-w-2xl space-y-3">
        {GUIDE_STEPS.map((item) => (
          <div
            className="flex gap-4 rounded-xl border border-white/10 bg-card p-5"
            key={item.step}
          >
            <span className="shrink-0 font-mono text-2xl font-bold text-white/10">{item.step}</span>
            <div>
              <p className="text-sm font-semibold text-foreground">{item.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{item.body}</p>
            </div>
          </div>
        ))}
      </div>
    </WorkflowPageShell>
  );
}
