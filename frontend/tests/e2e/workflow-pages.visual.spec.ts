import { expect, test, type Page } from '@playwright/test';

function seedWorkspace(page: Page, selectedMode: string | null) {
  return page.addInitScript((payload) => {
    window.localStorage.setItem(
      'nipe-workspace',
      JSON.stringify({
        state: payload,
        version: 0,
      }),
    );
  }, {
    projectId: 101,
    projectTitle: 'Shadow Slave PoC',
    selectedMode,
    chapterCount: 12,
    runId: 501,
  });
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/modes', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        modes: ['audiobook', 'academic', 'author', 'custom'],
        default_mode: 'audiobook',
        persisted_in: ['projects.selected_mode'],
      }),
    });
  });
});

test('captures visual evidence for mode selection page', async ({ page }, testInfo) => {
  await seedWorkspace(page, null);
  await page.goto('/projects/101/mode');

  await expect(page.getByTestId('mode-required-hint')).toBeVisible();
  const screenshot = await page.screenshot({ fullPage: true });
  expect(screenshot.byteLength).toBeGreaterThan(10_000);

  await testInfo.attach('mode-page.png', {
    body: screenshot,
    contentType: 'image/png',
  });
});

test('captures visual evidence for pipeline lock state', async ({ page }, testInfo) => {
  await seedWorkspace(page, null);
  await page.goto('/projects/101/pipeline-setup');

  await expect(page.getByTestId('mode-lock-hint')).toBeVisible();
  const screenshot = await page.screenshot({ fullPage: true });
  expect(screenshot.byteLength).toBeGreaterThan(10_000);

  await testInfo.attach('pipeline-lock-page.png', {
    body: screenshot,
    contentType: 'image/png',
  });
});
