import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  completeRouteNavigationMeasurement,
  PERFORMANCE_BUDGET_EXCEEDED_EVENT_NAME,
  PERFORMANCE_METRIC_EVENT_NAME,
  performanceBudgets,
  reportApiLatencyMetric,
  reportRenderCostMetric,
  resetRouteNavigationMeasurementForTests,
  startRouteNavigationMeasurement,
} from '@/features/workflow/performance/performance-instrumentation';

function trackCustomEventDetails(eventName: string) {
  const details: unknown[] = [];
  const handler = (event: Event) => {
    details.push((event as CustomEvent).detail);
  };
  window.addEventListener(eventName, handler as EventListener);
  return {
    details,
    cleanup: () => window.removeEventListener(eventName, handler as EventListener),
  };
}

describe('performance instrumentation', () => {
  afterEach(() => {
    resetRouteNavigationMeasurementForTests();
    vi.restoreAllMocks();
  });

  it('captures API latency metrics against configured budgets', () => {
    const metrics = trackCustomEventDetails(PERFORMANCE_METRIC_EVENT_NAME);
    const budgetExceeded = trackCustomEventDetails(PERFORMANCE_BUDGET_EXCEEDED_EVENT_NAME);

    const metric = reportApiLatencyMetric({
      method: 'get',
      path: '/api/projects',
      durationMs: 12,
      statusCode: 200,
      success: true,
    });

    metrics.cleanup();
    budgetExceeded.cleanup();

    expect(metric.kind).toBe('api_latency');
    expect(metric.budgetMs).toBe(performanceBudgets.apiLatencyMs);
    expect(metric.exceededBudget).toBe(false);
    expect(metric.metadata).toMatchObject({
      method: 'GET',
      path: '/api/projects',
      status_code: 200,
      success: true,
    });
    expect(metrics.details).toHaveLength(1);
    expect(budgetExceeded.details).toHaveLength(0);
  });

  it('captures route latency and emits budget-exceeded events when transitions are slow', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const metrics = trackCustomEventDetails(PERFORMANCE_METRIC_EVENT_NAME);
    const budgetExceeded = trackCustomEventDetails(PERFORMANCE_BUDGET_EXCEEDED_EVENT_NAME);

    startRouteNavigationMeasurement('/projects/42/setup', 100);
    const metric = completeRouteNavigationMeasurement(
      '/projects/42/setup',
      100 + performanceBudgets.routeLatencyMs + 5,
    );

    metrics.cleanup();
    budgetExceeded.cleanup();

    expect(metric).not.toBeNull();
    expect(metric?.kind).toBe('route_latency');
    expect(metric?.exceededBudget).toBe(true);
    expect(metrics.details).toHaveLength(1);
    expect(budgetExceeded.details).toHaveLength(1);
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it('captures render-cost metrics with component and route metadata', () => {
    const metrics = trackCustomEventDetails(PERFORMANCE_METRIC_EVENT_NAME);

    const metric = reportRenderCostMetric({
      component: 'main-shell-route-content',
      phase: 'update',
      actualDurationMs: 16,
      routePath: '/dashboard',
    });

    metrics.cleanup();

    expect(metric.kind).toBe('render_cost');
    expect(metric.budgetMs).toBe(performanceBudgets.renderCostMs);
    expect(metric.metadata).toMatchObject({
      component: 'main-shell-route-content',
      phase: 'update',
      route_path: '/dashboard',
    });
    expect(metrics.details).toHaveLength(1);
  });
});
