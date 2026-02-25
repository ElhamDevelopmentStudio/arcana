import { describe, expect, it } from "vitest";

import { resolveModeOptions } from "@/features/mode/mode-catalog";

describe("mode catalog regression checks", () => {
  it("keeps fallback ordering stable for null catalog", () => {
    expect(resolveModeOptions(null)).toEqual(["audiobook", "academic", "author", "custom"]);
  });

  it("keeps fallback ordering stable for empty catalog", () => {
    expect(
      resolveModeOptions({
        modes: [],
        default_mode: "audiobook",
        persisted_in: [],
      })
    ).toEqual(["audiobook", "academic", "author", "custom"]);
  });
});
