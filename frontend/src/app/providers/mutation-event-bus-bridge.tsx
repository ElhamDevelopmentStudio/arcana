import { useEffect, useRef } from 'react';

import { toast } from 'sonner';

import { useMutationEventBus } from '@/features/workflow/events/mutation-event-bus';

export function MutationEventBusBridge() {
  const nextEvent = useMutationEventBus((state) => state.queue[0]);
  const consume = useMutationEventBus((state) => state.consume);
  const handledEventIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!nextEvent) {
      return;
    }
    if (handledEventIds.current.has(nextEvent.id)) {
      consume(nextEvent.id);
      return;
    }
    handledEventIds.current.add(nextEvent.id);

    const notifier = nextEvent.level === 'success' ? toast.success : toast.error;
    notifier(nextEvent.title, {
      description: nextEvent.message,
      action:
        nextEvent.recoveryLabel && nextEvent.onRecovery
          ? {
              label: nextEvent.recoveryLabel,
              onClick: nextEvent.onRecovery,
            }
          : undefined,
    });

    consume(nextEvent.id);
  }, [consume, nextEvent]);

  return null;
}
