export const WORKFLOW_TELEMETRY_EVENT_NAME = 'nipe:workflow-telemetry';

export type WorkflowTelemetryStatus = 'success' | 'failure';

export type WorkflowTelemetryPayload = {
  action: string;
  method: string;
  path: string;
  status: WorkflowTelemetryStatus;
  status_code: number | null;
  error_message: string | null;
  emitted_at_iso: string;
};

export type WorkflowTelemetryInput = {
  method: string;
  path: string;
  success: boolean;
  statusCode?: number;
  errorMessage?: string;
};

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function normalizePath(path: string) {
  const withoutQuery = path.split('?')[0]?.trim() ?? '';
  if (withoutQuery.length === 0) {
    return '/unknown';
  }
  return withoutQuery
    .split('/')
    .filter((segment) => segment.length > 0)
    .map((segment) => {
      if (/^\d+$/.test(segment)) {
        return ':id';
      }
      if (/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(segment)) {
        return ':id';
      }
      return segment;
    })
    .join('/')
    .replace(/^/, '/');
}

function buildActionName(method: string, normalizedPath: string) {
  const pathAction = normalizedPath.replace(/^\/+/, '').replace(/[/-]+/g, '_');
  return `${method.toLowerCase()}_${pathAction || 'unknown'}`;
}

export function buildWorkflowTelemetryPayload(input: WorkflowTelemetryInput): WorkflowTelemetryPayload | null {
  const method = input.method.trim().toUpperCase();
  if (!MUTATING_METHODS.has(method)) {
    return null;
  }
  const normalizedPath = normalizePath(input.path);
  return {
    action: buildActionName(method, normalizedPath),
    method,
    path: normalizedPath,
    status: input.success ? 'success' : 'failure',
    status_code: input.statusCode ?? null,
    error_message: input.success ? null : input.errorMessage?.trim() || 'Unknown workflow mutation failure.',
    emitted_at_iso: new Date().toISOString(),
  };
}

export function reportWorkflowTelemetry(input: WorkflowTelemetryInput) {
  const payload = buildWorkflowTelemetryPayload(input);
  if (payload === null) {
    return null;
  }
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new CustomEvent(WORKFLOW_TELEMETRY_EVENT_NAME, { detail: payload }));
  }
  return payload;
}
