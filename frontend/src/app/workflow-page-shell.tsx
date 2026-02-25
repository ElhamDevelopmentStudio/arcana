import type { PropsWithChildren, ReactNode } from 'react';

import { Badge } from '@/components/ui/badge';

type WorkflowPageShellProps = PropsWithChildren<{
  title: string;
  description: string;
  step: string;
  action?: ReactNode;
}>;

export function WorkflowPageShell({ title, description, step, action, children }: WorkflowPageShellProps) {
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm lg:p-6">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3 border-b pb-4">
        <div>
          <Badge variant="secondary" className="mb-3">
            {step}
          </Badge>
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}
