export const PERFORMANCE_METRIC_EVENT_NAME = 'nipe:performance-metric';
export const PERFORMANCE_BUDGET_EXCEEDED_EVENT_NAME = 'nipe:performance-budget-exceeded';

export type PerformanceMetricKind = 'route_latency' | 'api_latency' | 'render_cost';

export type PerformanceMetric = {
  kind: PerformanceMetricKind;
  name: string;
  durationMs: number;
  budgetMs: number;
  exceededBudget: boolean;
  capturedAtIso: string;
  metadata: Record<string, unknown>;
};

export type ApiLatencyMetricInput = {
  method: string;
  path: string;
  durationMs: number;
  statusCode?: number;
  success: boolean;
};

export type RenderCostMetricInput = {
  component: string;
  phase: 'mount' | 'update' | 'nested-update';
  actualDurationMs: number;
  routePath?: string;
};

const DEFAULT_ROUTE_LATENCY_BUDGET_MS = 2_000;
const DEFAULT_API_LATENCY_BUDGET_MS = 3_000;
const DEFAULT_RENDER_COST_BUDGET_MS = 40;

type PendingRouteNavigation = {
  targetPath: string;
  startedAtMs: number;
};

let pendingRouteNavigation: PendingRouteNavigation | null = null;

function parseBudget(rawValue: unknown, fallback: number) {
  const parsedValue =
    typeof rawValue === 'number'
      ? rawValue
      : typeof rawValue === 'string'
        ? Number.parseInt(rawValue, 10)
        : Number.NaN;
  if (!Number.isFinite(parsedValue) || parsedValue <= 0) {
    return fallback;
  }
  return parsedValue;
}

function getNowMs() {
  if (typeof globalThis.performance?.now === 'function') {
    return globalThis.performance.now();
  }
  return Date.now();
}

function normalizePath(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : '/';
}

function buildMetric(
  kind: PerformanceMetricKind,
  name: string,
  durationMs: number,
  budgetMs: number,
  metadata: Record<string, unknown>,
): PerformanceMetric {
  const boundedDuration = Number.isFinite(durationMs) && durationMs >= 0 ? durationMs : 0;
  return {
    kind,
    name,
    durationMs: boundedDuration,
    budgetMs,
    exceededBudget: boundedDuration > budgetMs,
    capturedAtIso: new Date().toISOString(),
    metadata,
  };
}

function dispatchMetric(metric: PerformanceMetric) {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') {
    return;
  }
  window.dispatchEvent(new CustomEvent(PERFORMANCE_METRIC_EVENT_NAME, { detail: metric }));
  if (!metric.exceededBudget) {
    return;
  }
  window.dispatchEvent(new CustomEvent(PERFORMANCE_BUDGET_EXCEEDED_EVENT_NAME, { detail: metric }));
  if (typeof console.warn === 'function') {
    console.warn(
      `[performance-budget-exceeded] ${metric.kind}:${metric.name}=${metric.durationMs.toFixed(2)}ms budget=${metric.budgetMs}ms`,
      metric.metadata,
    );
  }
}

export const performanceBudgets = {
  routeLatencyMs: parseBudget(import.meta.env.VITE_ROUTE_LATENCY_BUDGET_MS, DEFAULT_ROUTE_LATENCY_BUDGET_MS),
  apiLatencyMs: parseBudget(import.meta.env.VITE_API_LATENCY_BUDGET_MS, DEFAULT_API_LATENCY_BUDGET_MS),
  renderCostMs: parseBudget(import.meta.env.VITE_RENDER_COST_BUDGET_MS, DEFAULT_RENDER_COST_BUDGET_MS),
};

export function reportApiLatencyMetric(input: ApiLatencyMetricInput) {
  const metric = buildMetric(
    'api_latency',
    `${input.method.toUpperCase()} ${input.path}`,
    input.durationMs,
    performanceBudgets.apiLatencyMs,
    {
      method: input.method.toUpperCase(),
      path: input.path,
      status_code: input.statusCode ?? null,
      success: input.success,
    },
  );
  dispatchMetric(metric);
  return metric;
}

export function reportRenderCostMetric(input: RenderCostMetricInput) {
  const metric = buildMetric(
    'render_cost',
    input.component,
    input.actualDurationMs,
    performanceBudgets.renderCostMs,
    {
      component: input.component,
      phase: input.phase,
      route_path: input.routePath ?? null,
    },
  );
  dispatchMetric(metric);
  return metric;
}

export function startRouteNavigationMeasurement(targetPath: string, startedAtMs: number = getNowMs()) {
  pendingRouteNavigation = {
    targetPath: normalizePath(targetPath),
    startedAtMs,
  };
}

export function completeRouteNavigationMeasurement(
  resolvedPath: string,
  finishedAtMs: number = getNowMs(),
) {
  if (!pendingRouteNavigation) {
    return null;
  }
  const normalizedResolvedPath = normalizePath(resolvedPath);
  if (pendingRouteNavigation.targetPath !== normalizedResolvedPath) {
    return null;
  }
  const durationMs = Math.max(0, finishedAtMs - pendingRouteNavigation.startedAtMs);
  pendingRouteNavigation = null;
  const metric = buildMetric(
    'route_latency',
    normalizedResolvedPath,
    durationMs,
    performanceBudgets.routeLatencyMs,
    {
      route_path: normalizedResolvedPath,
    },
  );
  dispatchMetric(metric);
  return metric;
}

export function resetRouteNavigationMeasurementForTests() {
  pendingRouteNavigation = null;
}
