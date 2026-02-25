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
    <section className="nipe-panel p-5 lg:p-6">
      <header className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-panel-border/75 pb-5">
        <div>
          <Badge variant="secondary" className="mb-3">
            {step}
          </Badge>
          <h2 className="text-2xl font-semibold tracking-tight text-panel-foreground lg:text-[1.9rem]">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
        {action}
      </header>
      <div className="space-y-4">{children}</div>
    </section>
  );
}
