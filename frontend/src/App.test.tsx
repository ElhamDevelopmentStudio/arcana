import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App, { pickModeFromCatalog, resolveModeOptions } from "./App";
import { resetUiStoreForTests } from "@/app/store/uiStore";
import { NipeApiClient } from "@/shared/api/http";

describe("MODE-004 post-ingestion mode selection UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetUiStoreForTests();

    vi.spyOn(NipeApiClient.prototype, "getModeCatalog").mockResolvedValue({
      modes: ["audiobook", "academic", "author", "custom"],
      default_mode: "audiobook",
      persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    resetUiStoreForTests();
  });

  it("unit: mode option helpers resolve and select expected values", () => {
    expect(resolveModeOptions(null)).toEqual(["audiobook", "academic", "author", "custom"]);

    const catalog = {
      modes: ["audiobook", "academic", "author", "custom"],
      default_mode: "academic",
      persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
    };

    expect(pickModeFromCatalog(catalog, "author")).toBe("author");
    expect(pickModeFromCatalog(catalog, "unknown")).toBe("academic");
  });

  it("integration: mode selector unlocks only after TXT ingestion", async () => {
    vi.spyOn(NipeApiClient.prototype, "createProject").mockResolvedValue({
      id: 1,
      title: "Mode Integration",
      selected_mode: "audiobook",
      created_at: "2026-02-24T00:00:00Z",
    });

    vi.spyOn(NipeApiClient.prototype, "ingestTxt").mockResolvedValue({
      project_id: 1,
      chapter_count: 2,
    });

    const user = userEvent.setup();
    render(<App />);

    const createButton = await screen.findByRole("button", { name: "Create Project" });
    await user.click(createButton);

    await screen.findByText(/Project ID: 1/);

    const modeSelect = await screen.findByTestId("mode-select");
    expect(modeSelect).toBeDisabled();

    const setupCard = await screen.findByTestId("project-setup-section");
    const txtInput = setupCard.querySelector<HTMLInputElement>('input[type="file"][accept=".txt"]');
    if (!txtInput) {
      throw new Error("TXT input not found");
    }
    const txtFile = new File(["Chapter 1\nSample"], "sample.txt", { type: "text/plain" });
    await user.upload(txtInput, txtFile);

    await user.click(within(setupCard).getByRole("button", { name: "Upload TXT" }));

    await screen.findByText(/Chapters detected: 2/);
    expect(await screen.findByText("Detected chapters: 2")).toBeInTheDocument();
    expect(await screen.findByTestId("mode-select")).not.toBeDisabled();

    const options = Array.from(within(await screen.findByTestId("mode-select")).getAllByRole("option")).map(
      (option) => option.textContent
    );
    expect(options).toEqual(["audiobook", "academic", "author", "custom"]);
  });

  it("e2e: selected mode is sent in run payload after ingestion", async () => {
    vi.spyOn(NipeApiClient.prototype, "createProject").mockResolvedValue({
      id: 1,
      title: "Mode E2E",
      selected_mode: "audiobook",
      created_at: "2026-02-24T00:00:00Z",
    });

    vi.spyOn(NipeApiClient.prototype, "ingestTxt").mockResolvedValue({
      project_id: 1,
      chapter_count: 2,
    });

    const runSpy = vi.spyOn(NipeApiClient.prototype, "runPipeline").mockResolvedValue({
      run_id: 7,
      project_id: 1,
      status: "completed",
      segment_count: 3,
    });

    vi.spyOn(NipeApiClient.prototype, "getRunDetail").mockResolvedValue({
      run_id: 7,
      project_id: 1,
      status: "completed",
      config: { mode: "author" },
      started_at: "2026-02-24T00:00:00Z",
      finished_at: "2026-02-24T00:00:01Z",
      segment_count: 3,
      llm_calls: [],
    });

    vi.spyOn(NipeApiClient.prototype, "getExport").mockResolvedValue({
      project_id: 1,
      project_title: "Mode E2E",
      run_id: 7,
      status: "completed",
      segments: [{ segment_id: "1-001" }],
    });

    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Create Project" }));
    await screen.findByText(/Project ID: 1/);

    const setupCard = await screen.findByTestId("project-setup-section");
    const txtInput = setupCard.querySelector<HTMLInputElement>('input[type="file"][accept=".txt"]');
    if (!txtInput) {
      throw new Error("TXT input not found");
    }

    await user.upload(txtInput, new File(["Chapter 1\nSample"], "sample.txt", { type: "text/plain" }));
    await user.click(within(setupCard).getByRole("button", { name: "Upload TXT" }));
    await screen.findByText(/Chapters detected: 2/);

    await user.selectOptions(await screen.findByTestId("mode-select"), "author");
    await user.click(await screen.findByRole("button", { name: "Run Pipeline" }));

    await screen.findByText(/Segments produced: 3/);

    await waitFor(() => {
      expect(runSpy).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          mode: "author",
        })
      );
    });
  });

  it("regression: fallback mode ordering remains stable", () => {
    expect(resolveModeOptions(null)).toEqual(["audiobook", "academic", "author", "custom"]);
  });
});
