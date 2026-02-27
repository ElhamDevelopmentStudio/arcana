import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { CreateProjectDialog } from '@/components/landing/create-project-dialog';

type HeroSectionProps = {
  healthStatus: string | null;
};

export function HeroSection({ healthStatus }: HeroSectionProps) {
  const navigate = useNavigate();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  return (
    <section className="relative overflow-hidden px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 rounded-3xl border border-panel-border/80 bg-card/85 p-8 shadow-sm lg:p-12">
        <div className="inline-flex w-fit items-center rounded-full border border-panel-border/80 bg-background/75 px-3 py-1 text-xs font-medium text-muted-foreground">
          Service status: <span className="ml-2 font-semibold text-foreground">{healthStatus ?? 'unavailable'}</span>
        </div>
        <div className="space-y-4">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Narrative Intelligence and Performance Engine
          </h1>
          <p className="max-w-3xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Create draft projects, ingest corpus files, choose processing modes, run pipelines, and export narrative
            analysis outputs from one shared workspace.
          </p>
          <p className="text-sm text-muted-foreground">
            Authentication is not enabled yet. This deployment runs as a no-auth shared workspace.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button data-testid="landing-enter-dashboard" onClick={() => navigate('/dashboard')}>
            Enter Dashboard
          </Button>
          <Button data-testid="landing-create-draft" onClick={() => setIsDialogOpen(true)} variant="outline">
            Create Draft Project
          </Button>
        </div>
      </div>
      <CreateProjectDialog open={isDialogOpen} onOpenChange={setIsDialogOpen} />
    </section>
  );
}

