import type { PropsWithChildren, ReactNode } from 'react';

type WorkflowPageShellProps = PropsWithChildren<{
  title: string;
  description: string;
  step: string;
  action?: ReactNode;
}>;

export function WorkflowPageShell({ title, description, step, action, children }: WorkflowPageShellProps) {
  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">{step}</p>
          <h2 className="text-2xl font-semibold tracking-tight text-panel-foreground lg:text-[1.9rem]">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
        {action}
      </header>
      <div className="space-y-4">{children}</div>
    </section>
  );
}
