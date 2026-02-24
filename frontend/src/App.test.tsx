import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App, { pickModeFromCatalog, resolveModeOptions } from "./App";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MODE-004 post-ingestion mode selection UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("unit: mode option helpers resolve and select expected values", () => {
    expect(resolveModeOptions(null)).toEqual(["audiobook", "academic", "author", "custom"]);

    const catalog = {
      modes: ["audiobook", "academic", "author", "custom"],
      default_mode: "academic",
      persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
    };
    expect(pickModeFromCatalog(catalog, "author")).toBe("author");
    expect(pickModeFromCatalog(catalog, "nonexistent")).toBe("academic");
  });

  it("integration: mode selector unlocks only after TXT ingestion", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          id: 1,
          title: "Mode Integration",
          selected_mode: "audiobook",
          created_at: "2026-02-24T00:00:00Z",
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          modes: ["audiobook", "academic", "author", "custom"],
          default_mode: "audiobook",
          persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
        })
      )
      .mockResolvedValueOnce(jsonResponse({ project_id: 1, chapter_count: 2 }));
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Create Project" }));
    await screen.findByText("Project created: 1");

    const modeSelect = screen.getByTestId("mode-select");
    expect(modeSelect).toBeDisabled();

    const setupCard = screen.getByText("1) Project Setup + TXT Upload").closest("section");
    if (!setupCard) {
      throw new Error("Setup card not found");
    }
    const txtInput = setupCard.querySelector<HTMLInputElement>('input[type="file"]');
    if (!txtInput) {
      throw new Error("TXT file input not found");
    }

    const txtFile = new File(["Chapter 1\nSample"], "sample.txt", { type: "text/plain" });
    await user.upload(txtInput, txtFile);
    await user.click(within(setupCard).getByRole("button", { name: "Upload TXT" }));

    await screen.findByText("TXT ingested. Chapters detected: 2");
    expect(screen.getByTestId("mode-select")).not.toBeDisabled();
    const options = Array.from(within(screen.getByTestId("mode-select")).getAllByRole("option")).map(
      (option) => option.textContent
    );
    expect(options).toEqual(["audiobook", "academic", "author", "custom"]);
  });

  it("e2e: selected mode is sent in run payload after ingestion", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          id: 1,
          title: "Mode E2E",
          selected_mode: "audiobook",
          created_at: "2026-02-24T00:00:00Z",
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          modes: ["audiobook", "academic", "author", "custom"],
          default_mode: "audiobook",
          persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
        })
      )
      .mockResolvedValueOnce(jsonResponse({ project_id: 1, chapter_count: 2 }))
      .mockResolvedValueOnce(jsonResponse({ run_id: 7, project_id: 1, status: "completed", segment_count: 3 }))
      .mockResolvedValueOnce(
        jsonResponse({
          run_id: 7,
          project_id: 1,
          status: "completed",
          config: { mode: "author" },
          started_at: "2026-02-24T00:00:00Z",
          finished_at: "2026-02-24T00:00:01Z",
          segment_count: 3,
          llm_calls: [],
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          project_id: 1,
          project_title: "Mode E2E",
          run_id: 7,
          status: "completed",
          segments: [{ segment_id: "1-001" }],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Create Project" }));
    await screen.findByText("Project created: 1");

    const setupCard = screen.getByText("1) Project Setup + TXT Upload").closest("section");
    if (!setupCard) {
      throw new Error("Setup card not found");
    }
    const txtInput = setupCard.querySelector<HTMLInputElement>('input[type="file"]');
    if (!txtInput) {
      throw new Error("TXT file input not found");
    }
    await user.upload(txtInput, new File(["Chapter 1\nSample"], "sample.txt", { type: "text/plain" }));
    await user.click(within(setupCard).getByRole("button", { name: "Upload TXT" }));
    await screen.findByText("TXT ingested. Chapters detected: 2");

    await user.selectOptions(screen.getByTestId("mode-select"), "author");
    await user.click(screen.getByRole("button", { name: "Run Pipeline" }));

    await waitFor(() => {
      expect(screen.getByText("Pipeline finished. Segments: 3")).toBeInTheDocument();
    });

    const runCall = fetchMock.mock.calls.find(([url, init]) => {
      return String(url).endsWith("/api/projects/1/runs") && (init as RequestInit | undefined)?.method === "POST";
    });
    if (!runCall) {
      throw new Error("Run API call not found");
    }

    const [, runInit] = runCall;
    const runPayload = JSON.parse(String((runInit as RequestInit).body));
    expect(runPayload.mode).toBe("author");
  });

  it("regression: fallback mode ordering remains stable", () => {
    expect(resolveModeOptions(null)).toEqual(["audiobook", "academic", "author", "custom"]);
  });
});
