import { useEffect, useRef } from 'react';

import { nipeApiClient } from '@/services/api-client';
import {
  isTerminalJobStatus,
  type LongRunningJobStatus,
  useJobNotificationStore,
} from '@/features/workflow/state/job-notification-store';

const ACTIVE_POLL_INTERVAL_MS = 1400;
const TERMINAL_RETENTION_MS = 3 * 60_000;

function toLongRunningJobStatus(value: string | null | undefined): LongRunningJobStatus {
  if (value === 'queued' || value === 'running' || value === 'completed' || value === 'failed' || value === 'cancelled') {
    return value;
  }
  return 'unknown';
}

export function useJobNotificationPoller() {
  const updateJob = useJobNotificationStore((state) => state.updateJob);
  const dismissTerminalJobs = useJobNotificationStore((state) => state.dismissTerminalJobs);
  const inFlightKeysRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const cleanupId = window.setInterval(() => {
      dismissTerminalJobs(TERMINAL_RETENTION_MS);
    }, 20_000);
    return () => window.clearInterval(cleanupId);
  }, [dismissTerminalJobs]);

  useEffect(() => {
    let isDisposed = false;

    const pollStatuses = async () => {
      const snapshot = useJobNotificationStore.getState().jobs;
      const activeJobs = snapshot.filter((job) => !isTerminalJobStatus(job.status));
      if (activeJobs.length === 0) {
        return;
      }

      await Promise.all(
        activeJobs.map(async (job) => {
          if (inFlightKeysRef.current.has(job.key)) {
            return;
          }
          inFlightKeysRef.current.add(job.key);

          try {
            if (job.type === 'ingestion') {
              const statusPayload = await nipeApiClient.getProjectIngestionJobStatus(job.projectId, job.jobId);
              if (isDisposed) {
                return;
              }
              updateJob({
                type: job.type,
                projectId: job.projectId,
                jobId: job.jobId,
                status: toLongRunningJobStatus(statusPayload.status),
                progress: statusPayload.progress,
                message: statusPayload.message ?? null,
                errorMessage: statusPayload.error_message ?? null,
                executorName: statusPayload.executor_name ?? null,
                taskId: statusPayload.task_id ?? null,
              });
              return;
            }

            if (job.type === 'extraction') {
              const statusPayload = await nipeApiClient.getCharacterExtractionJobStatus(job.projectId, job.jobId);
              if (isDisposed) {
                return;
              }
              updateJob({
                type: job.type,
                projectId: job.projectId,
                jobId: job.jobId,
                status: toLongRunningJobStatus(statusPayload.status),
                progress: statusPayload.progress,
                message: statusPayload.message ?? null,
                errorMessage: statusPayload.error_message ?? null,
                executorName: statusPayload.executor_name ?? null,
                taskId: statusPayload.task_id ?? null,
              });
              return;
            }

            const runId = Number(job.jobId);
            if (!Number.isInteger(runId) || runId <= 0) {
              updateJob({
                type: job.type,
                projectId: job.projectId,
                jobId: job.jobId,
                status: 'failed',
                errorMessage: 'Invalid run identifier.',
              });
              return;
            }
            const runDetail = await nipeApiClient.getRunDetail(job.projectId, runId);
            if (isDisposed) {
              return;
            }
            const runStatus = toLongRunningJobStatus(runDetail.status);
            updateJob({
              type: job.type,
              projectId: job.projectId,
              jobId: job.jobId,
              status: runStatus,
              progress: runStatus === 'completed' ? 100 : null,
              message:
                runStatus === 'running' || runStatus === 'queued'
                  ? 'Pipeline execution in progress'
                  : `Segments: ${runDetail.segment_count}`,
              errorMessage: runStatus === 'failed' ? 'Pipeline execution failed.' : null,
            });
          } catch {
            if (!isDisposed) {
              updateJob({
                type: job.type,
                projectId: job.projectId,
                jobId: job.jobId,
                status: 'unknown',
                message: 'Polling status…',
              });
            }
          } finally {
            inFlightKeysRef.current.delete(job.key);
          }
        }),
      );
    };

    void pollStatuses();
    const intervalId = window.setInterval(() => {
      void pollStatuses();
    }, ACTIVE_POLL_INTERVAL_MS);
    return () => {
      isDisposed = true;
      window.clearInterval(intervalId);
    };
  }, [updateJob]);
}
