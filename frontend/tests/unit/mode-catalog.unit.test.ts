import { describe, expect, it } from "vitest";

import { pickModeFromCatalog, resolveModeOptions } from "@/features/mode/mode-catalog";

describe("mode catalog helpers", () => {
  it("returns fallback ordering when catalog is null", () => {
    expect(resolveModeOptions(null)).toEqual(["audiobook", "academic", "author", "custom"]);
  });

  it("keeps preferred mode when it exists in catalog", () => {
    const catalog = {
      modes: ["audiobook", "academic", "author", "custom"],
      default_mode: "academic",
      persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
    };

    expect(pickModeFromCatalog(catalog, "author")).toBe("author");
  });

  it("falls back to default mode when preferred mode is missing", () => {
    const catalog = {
      modes: ["audiobook", "academic", "author", "custom"],
      default_mode: "academic",
      persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
    };

    expect(pickModeFromCatalog(catalog, "unknown")).toBe("academic");
  });
});
