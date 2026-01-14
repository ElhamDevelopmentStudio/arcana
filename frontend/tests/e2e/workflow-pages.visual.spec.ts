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
