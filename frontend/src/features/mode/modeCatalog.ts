import type { ModeCatalog } from "@/app/types";

const FALLBACK_MODES = ["audiobook", "academic", "author", "custom"] as const;

export function resolveModeOptions(catalog: ModeCatalog | null): string[] {
  if (!catalog || !Array.isArray(catalog.modes) || catalog.modes.length === 0) {
    return [...FALLBACK_MODES];
  }
  return catalog.modes;
}

export function pickModeFromCatalog(catalog: ModeCatalog, preferredMode?: string): string {
  const options = resolveModeOptions(catalog);
  if (preferredMode && options.includes(preferredMode)) {
    return preferredMode;
  }
  if (catalog.default_mode && options.includes(catalog.default_mode)) {
    return catalog.default_mode;
  }
  return options[0];
}

export { FALLBACK_MODES };
