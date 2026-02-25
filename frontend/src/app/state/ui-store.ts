import { create } from 'zustand';

type UiState = {
  isBusy: boolean;
  setBusy: (isBusy: boolean) => void;
};

export const useUiStore = create<UiState>((set) => ({
  isBusy: false,
  setBusy: (isBusy) => set({ isBusy }),
}));
