import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const features = [
  {
    title: 'Project lifecycle control',
    description: 'Draft, ingest, archive, and restore projects with backend-enforced action gating.',
  },
  {
    title: 'Mode-governed processing',
    description: 'Run audiobook, academic, author, and custom profiles with persisted run configuration snapshots.',
  },
  {
    title: 'Character and voice workflows',
    description: 'Manage character maps, pronunciation dictionaries, and voice policies before execution.',
  },
  {
    title: 'Run orchestration',
    description: 'Launch runs, rerun from snapshots, recover stale running states, and cancel active runs.',
  },
  {
    title: 'Export and analytics outputs',
    description: 'Use JSON/CSV exports and narrative dashboards for readiness, tension, polarity, and co-occurrence.',
  },
  {
    title: 'Activity and contract visibility',
    description: 'Track project timeline events and operate against stable endpoint contracts.',
  },
];

export function FeaturesSection() {
  return (
    <section className="px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-6xl space-y-4">
        <div className="space-y-2">
          <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">Platform capabilities</h2>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            The landing experience is wired to real backend contracts and reflects current workspace capabilities.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.title}>
              <CardHeader>
                <CardTitle className="text-lg">{feature.title}</CardTitle>
                <CardDescription>{feature.description}</CardDescription>
              </CardHeader>
              <CardContent />
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

