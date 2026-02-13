import { AlertCircleIcon, InboxIcon } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty';
import { Spinner } from '@/components/ui/spinner';

type ApiPanelLoadingProps = {
  title?: string;
  description?: string;
};

type ApiPanelEmptyProps = {
  title: string;
  description: string;
};

type ApiPanelErrorProps = {
  title: string;
  description: string;
  onRetry?: () => void;
  retryLabel?: string;
};

export function ApiPanelLoading({
  title = 'Loading',
  description = 'Fetching panel data from backend.',
}: ApiPanelLoadingProps) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-panel-border/70 bg-background/35 px-4 py-4">
      <Spinner className="size-4 text-muted-foreground" />
      <div className="space-y-0.5">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export function ApiPanelEmpty({ title, description }: ApiPanelEmptyProps) {
  return (
    <Empty className="border border-panel-border/70 p-6">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <InboxIcon className="size-4" />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent />
    </Empty>
  );
}

export function ApiPanelError({
  title,
  description,
  onRetry,
  retryLabel = 'Retry',
}: ApiPanelErrorProps) {
  return (
    <Alert className="rounded-xl border-destructive/35 bg-destructive/10" variant="destructive">
      <AlertCircleIcon className="size-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>{description}</p>
        {onRetry ? (
          <Button
            className="border-destructive/35 bg-transparent text-destructive hover:bg-destructive/15"
            onClick={onRetry}
            size="sm"
            variant="outline"
          >
            {retryLabel}
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
