import { beforeEach, describe, expect, it } from 'vitest';

import { useJobNotificationStore } from '@/features/workflow/state/job-notification-store';

describe('job notification store', () => {
  beforeEach(() => {
    useJobNotificationStore.getState().clearAll();
  });

  it('registers and updates long-running jobs', () => {
    const store = useJobNotificationStore.getState();

    store.registerJob({
      type: 'pipeline',
      projectId: 9,
      jobId: '41',
      status: 'running',
    });
    let jobs = useJobNotificationStore.getState().jobs;
    expect(jobs).toHaveLength(1);
    expect(jobs[0].status).toBe('running');

    store.updateJob({
      type: 'pipeline',
      projectId: 9,
      jobId: '41',
      status: 'completed',
      progress: 100,
    });

    jobs = useJobNotificationStore.getState().jobs;
    expect(jobs[0].status).toBe('completed');
    expect(jobs[0].progress).toBe(100);
    expect(jobs[0].terminalAt).not.toBeNull();
  });

  it('dismisses terminal jobs while preserving active jobs', () => {
    const store = useJobNotificationStore.getState();
    store.registerJob({ type: 'ingestion', projectId: 3, jobId: 'a', status: 'completed' });
    store.registerJob({ type: 'extraction', projectId: 3, jobId: 'b', status: 'running' });

    store.dismissTerminalJobs(0);
    const jobs = useJobNotificationStore.getState().jobs;
    expect(jobs).toHaveLength(1);
    expect(jobs[0].type).toBe('extraction');
  });
});
