import { Link } from 'react-router-dom';
import { CheckCircle2, Clock3, Loader2, X, XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useJobNotificationPoller } from '@/features/workflow/hooks/use-job-notification-poller';
import {
  isTerminalJobStatus,
  type LongRunningJobEntry,
  useJobNotificationStore,
} from '@/features/workflow/state/job-notification-store';
import { cn } from '@/lib/utils';

function statusIcon(job: LongRunningJobEntry) {
  if (job.status === 'completed') {
    return <CheckCircle2 size={14} className="text-green-400" />;
  }
  if (job.status === 'failed' || job.status === 'cancelled') {
    return <XCircle size={14} className="text-red-400" />;
  }
  if (job.status === 'queued') {
    return <Clock3 size={14} className="text-amber-400" />;
  }
  return <Loader2 size={14} className="animate-spin text-amber-400" />;
}

function statusLabel(job: LongRunningJobEntry): string {
  if (job.status === 'completed') {
    return 'Completed';
  }
  if (job.status === 'failed') {
    return 'Failed';
  }
  if (job.status === 'cancelled') {
    return 'Cancelled';
  }
  if (job.status === 'queued') {
    return 'Queued';
  }
  if (job.status === 'running') {
    return 'Running';
  }
  return 'Updating';
}

function jobTypeLabel(type: LongRunningJobEntry['type']): string {
  if (type === 'ingestion') {
    return 'Ingestion';
  }
  if (type === 'extraction') {
    return 'Extraction';
  }
  return 'Pipeline';
}

export function JobNotificationCenter() {
  useJobNotificationPoller();

  const jobs = useJobNotificationStore((state) => state.jobs);
  const dismissJob = useJobNotificationStore((state) => state.dismissJob);
  const dismissTerminalJobs = useJobNotificationStore((state) => state.dismissTerminalJobs);

  if (jobs.length === 0) {
    return null;
  }

  const terminalCount = jobs.filter((job) => isTerminalJobStatus(job.status)).length;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 w-[min(92vw,24rem)]">
      <div className="pointer-events-auto rounded-xl border border-white/10 bg-card/95 shadow-2xl backdrop-blur">
        <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
          <p className="text-xs font-semibold text-muted-foreground">
            Job notifications
          </p>
          {terminalCount > 0 && (
            <Button
              size="sm"
              variant="ghost"
              className="h-6 px-2 text-[11px] text-muted-foreground hover:text-foreground"
              onClick={() => dismissTerminalJobs(0)}
            >
              Clear finished
            </Button>
          )}
        </div>
        <div className="max-h-72 divide-y divide-white/5 overflow-y-auto">
          {jobs.map((job) => (
            <div className="flex items-start gap-2 px-3 py-2" key={job.key}>
              <div className="mt-0.5 shrink-0">{statusIcon(job)}</div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-foreground">
                  {jobTypeLabel(job.type)} · Project #{job.projectId}
                </p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {statusLabel(job)}
                  {typeof job.progress === 'number' && !isTerminalJobStatus(job.status) ? ` · ${job.progress}%` : ''}
                </p>
                {job.message && (
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground/80">{job.message}</p>
                )}
                {job.errorMessage && (
                  <p className="mt-0.5 truncate text-[11px] text-red-300">{job.errorMessage}</p>
                )}
                <Link
                  className={cn(
                    'mt-1 inline-block text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline',
                  )}
                  to={job.href}
                >
                  View details
                </Link>
              </div>
              <button
                aria-label="Dismiss notification"
                className="shrink-0 rounded p-1 text-muted-foreground hover:bg-white/10 hover:text-foreground"
                onClick={() => dismissJob(job.key)}
                type="button"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
