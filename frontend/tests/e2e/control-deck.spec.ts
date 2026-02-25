import { expect, test } from "@playwright/test";

const modeCatalog = {
  modes: ["audiobook", "academic", "author", "custom"],
  default_mode: "audiobook",
  persisted_in: ["projects.selected_mode", "runs.config_json.mode"],
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/modes", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(modeCatalog),
    });
  });

  await page.route("**/api/projects", async (route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        title: "Shadow Slave PoC",
        selected_mode: "audiobook",
        created_at: "2026-02-24T00:00:00Z",
      }),
    });
  });

  await page.route("**/api/projects/1/ingest/txt", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        project_id: 1,
        chapter_count: 2,
      }),
    });
  });

  await page.route("**/api/projects/1/characters/import", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        project_id: 1,
        imported_count: 4,
      }),
    });
  });

  await page.route("**/api/projects/1/voices", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        project_id: 1,
        voice_config: {
          narrator_voice: "narrator_default",
          male_default_voice: "male_default",
          female_default_voice: "female_default",
        },
      }),
    });
  });

  await page.route("**/api/projects/1/runs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: 7,
        project_id: 1,
        status: "completed",
        segment_count: 3,
      }),
    });
  });

  await page.route("**/api/projects/1/runs/7", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: 7,
        project_id: 1,
        status: "completed",
        config: { mode: "author" },
        started_at: "2026-02-24T00:00:00Z",
        finished_at: "2026-02-24T00:00:01Z",
        segment_count: 3,
        llm_calls: [],
      }),
    });
  });

  await page.route("**/api/projects/1/exports/7.json", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        project_id: 1,
        project_title: "Shadow Slave PoC",
        run_id: 7,
        status: "completed",
        segments: [{ segment_id: "1-001" }],
      }),
    });
  });
});

test("visual: control deck renders branded layout", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "NIPE Control Deck" })).toBeVisible();
  await expect(page).toHaveScreenshot("control-deck-initial.png", { fullPage: true });
});

test("e2e+visual: create, ingest, run and export flow", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Create Project" }).click();
  await expect(page.getByText("Project ID: 1")).toBeVisible();

  await page.locator('input[type="file"][accept=".txt"]').setInputFiles({
    name: "sample.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Chapter 1\nSample text"),
  });

  await page.getByRole("button", { name: "Upload TXT" }).click();
  await expect(page.getByText("Chapters detected: 2")).toBeVisible();

  await expect(page.getByTestId("mode-select")).toBeEnabled();
  await page.getByTestId("mode-select").selectOption("author");

  await page.getByRole("button", { name: "Run Pipeline" }).click();
  await expect(page.getByText("Segments produced: 3")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Export JSON" })).toBeVisible();

  await expect(page).toHaveScreenshot("control-deck-after-run.png", { fullPage: true });
});
