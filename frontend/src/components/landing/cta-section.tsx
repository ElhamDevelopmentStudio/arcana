import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { CreateProjectDialog } from '@/components/landing/create-project-dialog';

export function CTASection() {
  const navigate = useNavigate();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  return (
    <section className="px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-6xl rounded-3xl border border-panel-border/80 bg-card p-8 shadow-sm lg:p-10">
        <div className="space-y-3">
          <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            Start the workspace flow
          </h2>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            Enter dashboard for control-panel operations, or create a draft project and continue with ingestion and
            mode setup later.
          </p>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button data-testid="landing-cta-dashboard" onClick={() => navigate('/dashboard')}>
            Enter Dashboard
          </Button>
          <Button data-testid="landing-cta-create-draft" onClick={() => setIsDialogOpen(true)} variant="outline">
            Create Draft Project
          </Button>
        </div>
      </div>
      <CreateProjectDialog open={isDialogOpen} onOpenChange={setIsDialogOpen} />
    </section>
  );
}

