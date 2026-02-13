import { beforeEach, describe, expect, it } from 'vitest';

import { useMutationEventBus } from '@/features/workflow/events/mutation-event-bus';

describe('mutation event bus', () => {
  beforeEach(() => {
    useMutationEventBus.getState().clear();
  });

  it('publishes and consumes mutation events', () => {
    const published = useMutationEventBus.getState().publish({
      level: 'success',
      title: 'Created',
      message: 'Draft project is ready.',
    });

    expect(useMutationEventBus.getState().queue).toHaveLength(1);
    expect(useMutationEventBus.getState().queue[0]?.id).toBe(published.id);

    useMutationEventBus.getState().consume(published.id);

    expect(useMutationEventBus.getState().queue).toHaveLength(0);
  });

  it('keeps queue bounded to the most recent entries', () => {
    for (let index = 0; index < 30; index += 1) {
      useMutationEventBus.getState().publish({
        level: 'error',
        title: `Error ${index}`,
        message: 'Failure',
      });
    }

    expect(useMutationEventBus.getState().queue).toHaveLength(20);
    expect(useMutationEventBus.getState().queue[0]?.title).toBe('Error 10');
    expect(useMutationEventBus.getState().queue[19]?.title).toBe('Error 29');
  });
});
