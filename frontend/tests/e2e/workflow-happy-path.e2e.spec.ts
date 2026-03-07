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
        selected_modes: ['audiobook'],
        llm_enabled: false,
        configuration_snapshot_id: 'project-101-config-initial',
        ingestion_timestamp: null,
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

  await page.route('**/api/projects/101/mode', async (route) => {
    if (route.request().method() !== 'PUT') {
      await route.fallback();
      return;
    }
    const payload = route.request().postDataJSON() as { mode?: string };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        project_id: 101,
        previous_mode: 'audiobook',
        selected_mode: payload.mode ?? 'audiobook',
        selected_modes: ['audiobook', payload.mode ?? 'audiobook'],
        chapter_count: 12,
        reused_ingested_corpus: true,
        stale_runs_marked: 1,
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
        persisted_in: ['projects.selected_mode', 'runs.config_json.mode'],
        mode_profiles: {
          audiobook: {
            max_segment_chars: 120,
            llm_enabled: false,
            provider_name: 'openrouter',
            max_calls_per_day: 25,
            llm_confidence_threshold: 0.6,
            web_scraping_enabled: false,
            speaker_confidence_threshold: 0.6,
            high_ambiguity_dialogue_flag_threshold: 2,
            unstable_emotion_shift_transition_threshold: 4,
            unstable_emotion_shift_density_threshold: 0.5,
            deep_semantic_refinement: false,
            deterministic_mode: false,
            profile_intent: 'tts-ready segmentation and stable narration defaults',
          },
          academic: {
            max_segment_chars: 220,
            llm_enabled: false,
            provider_name: 'openrouter',
            max_calls_per_day: 25,
            llm_confidence_threshold: 0.6,
            web_scraping_enabled: false,
            speaker_confidence_threshold: 0.6,
            high_ambiguity_dialogue_flag_threshold: 2,
            unstable_emotion_shift_transition_threshold: 4,
            unstable_emotion_shift_density_threshold: 0.5,
            deep_semantic_refinement: false,
            deterministic_mode: false,
            profile_intent: 'longer analytical segments for metric-friendly aggregation',
          },
          author: {
            max_segment_chars: 160,
            llm_enabled: false,
            provider_name: 'openrouter',
            max_calls_per_day: 25,
            llm_confidence_threshold: 0.6,
            web_scraping_enabled: false,
            speaker_confidence_threshold: 0.6,
            high_ambiguity_dialogue_flag_threshold: 2,
            unstable_emotion_shift_transition_threshold: 4,
            unstable_emotion_shift_density_threshold: 0.5,
            deep_semantic_refinement: false,
            deterministic_mode: false,
            profile_intent: 'balanced segmentation for narrative-health diagnostics',
          },
          custom: {
            max_segment_chars: 255,
            llm_enabled: false,
            provider_name: 'openrouter',
            max_calls_per_day: 25,
            llm_confidence_threshold: 0.6,
            web_scraping_enabled: false,
            speaker_confidence_threshold: 0.6,
            high_ambiguity_dialogue_flag_threshold: 2,
            unstable_emotion_shift_transition_threshold: 4,
            unstable_emotion_shift_density_threshold: 0.5,
            deep_semantic_refinement: false,
            deterministic_mode: false,
            profile_intent: 'user-tuned baseline with conservative defaults',
          },
        },
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
  await page.getByTestId('mode-switch-confirm-submit').click();
  await page.getByTestId('mode-continue-button').click();
  await expect(page).toHaveURL(/\/projects\/101\/characters$/);
});
