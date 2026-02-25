import { create } from "zustand";

export type ToastKind = "success" | "error" | "info";

export type ToastMessage = {
  id: string;
  kind: ToastKind;
  title: string;
  detail?: string;
};

type UiStoreState = {
  isBusy: boolean;
  messages: ToastMessage[];
  setBusy: (busy: boolean) => void;
  pushMessage: (message: Omit<ToastMessage, "id">) => void;
  removeMessage: (id: string) => void;
  clearMessages: () => void;
};

const initialUiState = {
  isBusy: false,
  messages: [],
} as const;

export const useUiStore = create<UiStoreState>((set) => ({
  ...initialUiState,
  setBusy: (busy) => set({ isBusy: busy }),
  pushMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id:
            typeof crypto !== "undefined" && "randomUUID" in crypto
              ? crypto.randomUUID()
              : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        },
      ],
    })),
  removeMessage: (id) => set((state) => ({ messages: state.messages.filter((item) => item.id !== id) })),
  clearMessages: () => set({ messages: [] }),
}));

export function resetUiStoreForTests() {
  useUiStore.setState(initialUiState);
}
