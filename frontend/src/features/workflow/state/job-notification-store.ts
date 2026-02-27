import { create } from 'zustand';

export type LongRunningJobType = 'ingestion' | 'extraction' | 'pipeline';
export type LongRunningJobStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'unknown';

export type LongRunningJobEntry = {
  key: string;
  type: LongRunningJobType;
  projectId: number;
  jobId: string;
  status: LongRunningJobStatus;
  progress: number | null;
  message: string | null;
  errorMessage: string | null;
  executorName: string | null;
  taskId: string | null;
  href: string;
  createdAt: number;
  updatedAt: number;
  terminalAt: number | null;
};

export type RegisterLongRunningJobInput = {
  type: LongRunningJobType;
  projectId: number;
  jobId: string;
  status?: LongRunningJobStatus;
  href?: string;
  message?: string | null;
};

export type UpdateLongRunningJobInput = {
  type: LongRunningJobType;
  projectId: number;
  jobId: string;
  status: LongRunningJobStatus;
  progress?: number | null;
  message?: string | null;
  errorMessage?: string | null;
  executorName?: string | null;
  taskId?: string | null;
};

type JobNotificationStoreState = {
  jobs: LongRunningJobEntry[];
  registerJob: (input: RegisterLongRunningJobInput) => void;
  updateJob: (input: UpdateLongRunningJobInput) => void;
  dismissJob: (jobKey: string) => void;
  dismissTerminalJobs: (olderThanMs?: number) => void;
  clearAll: () => void;
};

function buildJobKey(type: LongRunningJobType, projectId: number, jobId: string): string {
  return `${type}:${projectId}:${jobId}`;
}

function buildDefaultHref(type: LongRunningJobType, projectId: number): string {
  if (type === 'ingestion') {
    return `/projects/${projectId}/setup`;
  }
  if (type === 'extraction') {
    return `/projects/${projectId}/characters`;
  }
  return `/projects/${projectId}/runs`;
}

export function isTerminalJobStatus(status: LongRunningJobStatus): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

function normalizeProgress(progress: number | null | undefined): number | null {
  if (progress === null || progress === undefined || Number.isNaN(progress)) {
    return null;
  }
  return Math.max(0, Math.min(Math.trunc(progress), 100));
}

export const useJobNotificationStore = create<JobNotificationStoreState>()((set) => ({
  jobs: [],
  registerJob: (input) => {
    const projectId = Number(input.projectId);
    const normalizedJobId = String(input.jobId || '').trim();
    if (!Number.isInteger(projectId) || projectId <= 0 || !normalizedJobId) {
      return;
    }
    const jobKey = buildJobKey(input.type, projectId, normalizedJobId);
    const now = Date.now();
    const nextStatus = input.status ?? 'queued';

    set((state) => {
      const existingIndex = state.jobs.findIndex((job) => job.key === jobKey);
      if (existingIndex === -1) {
        const nextEntry: LongRunningJobEntry = {
          key: jobKey,
          type: input.type,
          projectId,
          jobId: normalizedJobId,
          status: nextStatus,
          progress: null,
          message: input.message ?? null,
          errorMessage: null,
          executorName: null,
          taskId: null,
          href: input.href ?? buildDefaultHref(input.type, projectId),
          createdAt: now,
          updatedAt: now,
          terminalAt: isTerminalJobStatus(nextStatus) ? now : null,
        };
        return { jobs: [nextEntry, ...state.jobs].slice(0, 24) };
      }

      const existing = state.jobs[existingIndex];
      const updated: LongRunningJobEntry = {
        ...existing,
        status: nextStatus,
        message: input.message ?? existing.message,
        href: input.href ?? existing.href,
        updatedAt: now,
        terminalAt: isTerminalJobStatus(nextStatus) ? now : null,
      };
      const nextJobs = [...state.jobs];
      nextJobs[existingIndex] = updated;
      nextJobs.sort((a, b) => b.updatedAt - a.updatedAt);
      return { jobs: nextJobs.slice(0, 24) };
    });
  },
  updateJob: (input) => {
    const projectId = Number(input.projectId);
    const normalizedJobId = String(input.jobId || '').trim();
    if (!Number.isInteger(projectId) || projectId <= 0 || !normalizedJobId) {
      return;
    }
    const jobKey = buildJobKey(input.type, projectId, normalizedJobId);
    const now = Date.now();

    set((state) => {
      const existingIndex = state.jobs.findIndex((job) => job.key === jobKey);
      const nextStatus = input.status;
      if (existingIndex === -1) {
        const nextEntry: LongRunningJobEntry = {
          key: jobKey,
          type: input.type,
          projectId,
          jobId: normalizedJobId,
          status: nextStatus,
          progress: normalizeProgress(input.progress),
          message: input.message ?? null,
          errorMessage: input.errorMessage ?? null,
          executorName: input.executorName ?? null,
          taskId: input.taskId ?? null,
          href: buildDefaultHref(input.type, projectId),
          createdAt: now,
          updatedAt: now,
          terminalAt: isTerminalJobStatus(nextStatus) ? now : null,
        };
        return { jobs: [nextEntry, ...state.jobs].slice(0, 24) };
      }

      const existing = state.jobs[existingIndex];
      const updated: LongRunningJobEntry = {
        ...existing,
        status: nextStatus,
        progress: normalizeProgress(input.progress ?? existing.progress),
        message: input.message ?? existing.message,
        errorMessage: input.errorMessage ?? existing.errorMessage,
        executorName: input.executorName ?? existing.executorName,
        taskId: input.taskId ?? existing.taskId,
        updatedAt: now,
        terminalAt: isTerminalJobStatus(nextStatus) ? now : null,
      };
      const nextJobs = [...state.jobs];
      nextJobs[existingIndex] = updated;
      nextJobs.sort((a, b) => b.updatedAt - a.updatedAt);
      return { jobs: nextJobs.slice(0, 24) };
    });
  },
  dismissJob: (jobKey) =>
    set((state) => ({
      jobs: state.jobs.filter((job) => job.key !== jobKey),
    })),
  dismissTerminalJobs: (olderThanMs = 5 * 60_000) =>
    set((state) => {
      const cutoff = Date.now() - Math.max(0, olderThanMs);
      return {
        jobs: state.jobs.filter((job) => job.terminalAt === null || job.terminalAt > cutoff),
      };
    }),
  clearAll: () => set({ jobs: [] }),
}));
