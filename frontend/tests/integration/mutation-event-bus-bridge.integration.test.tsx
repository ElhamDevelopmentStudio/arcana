import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MutationEventBusBridge } from '@/app/providers/mutation-event-bus-bridge';
import { useMutationEventBus } from '@/features/workflow/events/mutation-event-bus';

const toastSuccessMock = vi.fn();
const toastErrorMock = vi.fn();

vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccessMock(...args),
    error: (...args: unknown[]) => toastErrorMock(...args),
  },
}));

describe('mutation event bus bridge', () => {
  beforeEach(() => {
    toastSuccessMock.mockReset();
    toastErrorMock.mockReset();
    useMutationEventBus.getState().clear();
  });

  it('dispatches success events to toast.success', () => {
    useMutationEventBus.getState().publish({
      level: 'success',
      title: 'Draft project created',
      message: 'Project #101 is ready for ingestion.',
    });

    render(<MutationEventBusBridge />);

    expect(toastSuccessMock).toHaveBeenCalledTimes(1);
    expect(toastSuccessMock.mock.calls[0]?.[0]).toBe('Draft project created');
  });

  it('dispatches error events with recovery action', () => {
    const recoverMock = vi.fn();
    useMutationEventBus.getState().publish({
      level: 'error',
      title: 'Run cancellation failed',
      message: 'Network error',
      recoveryLabel: 'Reload app',
      onRecovery: recoverMock,
    });

    render(<MutationEventBusBridge />);

    expect(toastErrorMock).toHaveBeenCalledTimes(1);
    const options = toastErrorMock.mock.calls[0]?.[1] as
      | { action?: { onClick?: () => void } }
      | undefined;
    expect(options?.action).toBeDefined();
    options?.action?.onClick?.();
    expect(recoverMock).toHaveBeenCalledTimes(1);
  });
});
