import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { ProjectControlPanelSummaryResponseDto } from '@/app/schemas/api';

type StatsSectionProps = {
  summary: ProjectControlPanelSummaryResponseDto | null;
};

function resolveStateCount(summary: ProjectControlPanelSummaryResponseDto | null, lifecycleState: string): number {
  if (!summary) {
    return 0;
  }
  const row = summary.project_counts_by_state.find((item) => item.lifecycle_state === lifecycleState);
  return row?.project_count ?? 0;
}

export function StatsSection({ summary }: StatsSectionProps) {
  const cards = [
    {
      label: 'Total projects',
      value: summary?.total_projects ?? 0,
      description: 'All projects in the shared workspace.',
    },
    {
      label: 'Running now',
      value: summary?.active_run_count ?? 0,
      description: 'Projects with queued/running pipeline activity.',
    },
    {
      label: 'Completed',
      value: resolveStateCount(summary, 'completed'),
      description: 'Projects currently in completed lifecycle state.',
    },
    {
      label: 'Needs attention',
      value: summary?.recent_failure_count ?? 0,
      description: 'Recent run failures requiring review.',
    },
  ];

  return (
    <section className="px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto grid w-full max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Card key={card.label}>
            <CardHeader className="gap-1">
              <CardDescription>{card.label}</CardDescription>
              <CardTitle className="text-3xl">{card.value.toLocaleString()}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{card.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

