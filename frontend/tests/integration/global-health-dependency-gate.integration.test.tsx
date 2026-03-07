import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mutateHealthMock = vi.fn();
const useHealthQueryMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useHealthQuery: (...args: Parameters<typeof useHealthQueryMock>) => useHealthQueryMock(...args),
}));

import { AppProviders } from '@/app/providers/app-providers';

describe('global health dependency gate', () => {
  beforeEach(() => {
    mutateHealthMock.mockReset();
    useHealthQueryMock.mockReset();
  });

  it('renders children without a global alert when backend is healthy', () => {
    useHealthQueryMock.mockReturnValue({
      data: { status: 'ok' },
      error: undefined,
      mutate: mutateHealthMock,
    });

    render(
      <AppProviders>
        <button type="button">Pipeline action</button>
      </AppProviders>,
    );

    expect(screen.getByRole('button', { name: 'Pipeline action' })).toBeInTheDocument();
    expect(screen.queryByTestId('global-health-gate-alert')).not.toBeInTheDocument();
  });

  it('shows a blocking alert when health status is not ok and retries on demand', async () => {
    const user = userEvent.setup();
    useHealthQueryMock.mockReturnValue({
      data: { status: 'degraded' },
      error: undefined,
      mutate: mutateHealthMock,
    });

    render(
      <AppProviders>
        <button type="button">Pipeline action</button>
      </AppProviders>,
    );

    expect(screen.getByTestId('global-health-gate-alert')).toBeInTheDocument();
    expect(screen.getByTestId('global-health-gate-content')).toHaveClass('pointer-events-none');

    await user.click(screen.getByTestId('global-health-gate-retry'));

    expect(mutateHealthMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('global-health-gate-detail').textContent).toContain('degraded');
  });

  it('shows a blocking alert when health endpoint is unreachable', () => {
    useHealthQueryMock.mockReturnValue({
      data: undefined,
      error: new Error('Network error'),
      mutate: mutateHealthMock,
    });

    render(
      <AppProviders>
        <button type="button">Pipeline action</button>
      </AppProviders>,
    );

    expect(screen.getByTestId('global-health-gate-alert')).toBeInTheDocument();
    expect(screen.getByTestId('global-health-gate-detail').textContent).toContain('Network error');
  });
});
