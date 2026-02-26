import { Info } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { PropsWithChildren, ReactNode } from 'react';

type WorkflowPageShellProps = PropsWithChildren<{
  title: string;
  description: string;
  step: string;
  showOutputDisclaimer?: boolean;
  action?: ReactNode;
}>;

function OutputDisclaimer() {
  return (
    <Alert className="mt-3 max-w-3xl" data-testid="output-probabilistic-disclaimer">
      <Info className="size-4" />
      <AlertTitle>AI outputs are probabilistic, not perfect</AlertTitle>
      <AlertDescription>
        Model-derived content, tags, and metrics may be wrong or incomplete. Review and correct outputs before export or downstream use.
      </AlertDescription>
    </Alert>
  );
}

export function WorkflowPageShell({ title, description, step, action, showOutputDisclaimer, children }: WorkflowPageShellProps) {
  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">{step}</p>
          <h2 className="text-2xl font-semibold tracking-tight text-panel-foreground lg:text-[1.9rem]">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
          {showOutputDisclaimer ? <OutputDisclaimer /> : null}
        </div>
        {action}
      </header>
      <div className="space-y-4">{children}</div>
    </section>
  );
}
