import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const fixtureFilePath = path.resolve(currentDir, '../fixtures/minimal-novel.txt');

test.beforeEach(async ({ page }) => {
  await page.route('**/api/projects', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 101,
        title: 'Shadow Slave PoC',
        selected_mode: 'audiobook',
        created_at: '2026-02-25T00:00:00Z',
      }),
    });
  });

  await page.route('**/api/projects/101/ingest/txt', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        project_id: 101,
        chapter_count: 12,
      }),
    });
  });

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

test('creates project, ingests text, selects mode, and advances to character page', async ({ page }) => {
  await page.goto('/projects/new');

  await page.getByTestId('project-title-input').fill('Shadow Slave PoC');
  await page.getByTestId('create-project-button').click();
  await expect(page.getByTestId('project-created-state')).toContainText('101');

  await page.getByTestId('txt-upload-input').setInputFiles(fixtureFilePath);
  await page.getByTestId('upload-txt-button').click();
  await expect(page.getByTestId('chapter-count-state')).toContainText('12');

  await page.getByRole('button', { name: 'Continue to Mode Selection' }).click();
  await expect(page).toHaveURL(/\/projects\/101\/mode$/);

  await page.getByTestId('mode-select').selectOption('author');
  await page.getByTestId('mode-continue-button').click();
  await expect(page).toHaveURL(/\/projects\/101\/characters$/);
});
