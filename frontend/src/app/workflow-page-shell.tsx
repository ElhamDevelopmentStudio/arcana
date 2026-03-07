import { Info } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useId, type PropsWithChildren, type ReactNode } from 'react';

type WorkflowPageShellProps = PropsWithChildren<{
  title: string;
  description?: string;
  step?: string;
  breadcrumb?: string;
  showOutputDisclaimer?: boolean;
  action?: ReactNode;
}>;

function OutputDisclaimer() {
  return (
    <Alert className="mt-3 max-w-3xl border-white/10 bg-card" data-testid="output-probabilistic-disclaimer">
      <Info className="size-4" />
      <AlertTitle>AI outputs are probabilistic</AlertTitle>
      <AlertDescription>
        Model-derived content, tags, and metrics may be wrong or incomplete. Review outputs before export.
      </AlertDescription>
    </Alert>
  );
}

export function WorkflowPageShell({ title, description, breadcrumb, action, showOutputDisclaimer, children }: WorkflowPageShellProps) {
  const headingId = useId();
  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="flex-1 p-6 lg:p-8">
        <section aria-labelledby={headingId} className="space-y-6">
          <header className="space-y-1">
            {breadcrumb ? (
              <p className="text-xs text-muted-foreground">{breadcrumb}</p>
            ) : null}
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-foreground" id={headingId}>
                  {title}
                </h1>
                {description ? (
                  <p className="mt-1 text-sm text-muted-foreground">{description}</p>
                ) : null}
                {showOutputDisclaimer ? <OutputDisclaimer /> : null}
              </div>
              {action ? <div className="shrink-0">{action}</div> : null}
            </div>
            <div className="border-b border-white/10 pt-4" />
          </header>
          <div className="space-y-5">{children}</div>
        </section>
      </div>
    </div>
  );
}
