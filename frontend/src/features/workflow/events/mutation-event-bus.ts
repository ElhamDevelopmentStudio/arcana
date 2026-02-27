import { create } from 'zustand';

export type MutationEventLevel = 'success' | 'error';

export type MutationEvent = {
  id: string;
  level: MutationEventLevel;
  title: string;
  message: string;
  recoveryLabel?: string;
  onRecovery?: () => void;
  createdAt: number;
};

export type PublishMutationEventInput = {
  level: MutationEventLevel;
  title: string;
  message: string;
  recoveryLabel?: string;
  onRecovery?: () => void;
};

type MutationEventBusState = {
  queue: MutationEvent[];
  publish: (event: PublishMutationEventInput) => MutationEvent;
  consume: (eventId: string) => void;
  clear: () => void;
};

let mutationEventSequence = 0;

function nextMutationEventId() {
  mutationEventSequence += 1;
  return `mutation-event-${mutationEventSequence}`;
}

export const useMutationEventBus = create<MutationEventBusState>()((set) => ({
  queue: [],
  publish: (event) => {
    const nextEvent: MutationEvent = {
      id: nextMutationEventId(),
      level: event.level,
      title: event.title,
      message: event.message,
      recoveryLabel: event.recoveryLabel,
      onRecovery: event.onRecovery,
      createdAt: Date.now(),
    };
    set((state) => ({
      queue: [...state.queue.slice(-19), nextEvent],
    }));
    return nextEvent;
  },
  consume: (eventId) =>
    set((state) => ({
      queue: state.queue.filter((entry) => entry.id !== eventId),
    })),
  clear: () => set({ queue: [] }),
}));
