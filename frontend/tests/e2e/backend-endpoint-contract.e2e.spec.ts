import { createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

type WorkspaceState = {
  state: {
    projectId: number | null;
    chapterCount: number | null;
    runId: number | null;
    selectedMode: string | null;
  };
};

type ProjectResponse = {
  id: number;
  selected_mode: string;
};

type ModeCatalogResponse = {
  modes: string[];
  default_mode: string;
  persisted_in: string[];
  mode_profiles: Record<string, { max_segment_chars: number; llm_enabled: boolean; provider_name: string }>;
};

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const fixtureNovelPath = path.resolve(currentDir, '../fixtures/minimal-novel.txt');
const fixtureCharactersPath = path.resolve(currentDir, '../fixtures/characters-minimal.json');
const backendBaseUrl = process.env.BACKEND_BASE_URL ?? 'http://127.0.0.1:8000';

function uniqueTitle(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 9_999_999_9)}`;
}

async function readWorkspaceState(page: Parameters<typeof test>[0]['page']): Promise<WorkspaceState['state'] | null> {
  const rawState = await page.evaluate(() => window.localStorage.getItem('nipe-workspace'));
  if (!rawState) {
    return null;
  }

  const parsed = JSON.parse(rawState) as WorkspaceState;
  return parsed.state ?? null;
}

async function createProject(request: Parameters<typeof test>[0]['request'], title: string): Promise<ProjectResponse> {
  const createResponse = await request.post(`${backendBaseUrl}/api/projects`, {
    data: { title },
  });
  expect(createResponse.status()).toBe(201);
  return createResponse.json() as Promise<ProjectResponse>;
}

test.describe('backend real endpoint contract (frontend-integrated)', () => {
  test('endpoint contracts with success and validation failures are exercised against live backend', async ({ request }) => {
    const healthResponse = await request.get(`${backendBaseUrl}/health`);
    expect(healthResponse.status()).toBe(200);
    const healthPayload = (await healthResponse.json()) as { status: string };
    expect(healthPayload.status).toBe('ok');

    const modesResponse = await request.get(`${backendBaseUrl}/api/modes`);
    expect(modesResponse.status()).toBe(200);
    const modesPayload = (await modesResponse.json()) as ModeCatalogResponse;
    expect(modesPayload.modes).toEqual(expect.arrayContaining(['audiobook', 'academic', 'author', 'custom']));

    const missingProjectTitle = await request.post(`${backendBaseUrl}/api/projects`, { data: { title: '' } });
    expect(missingProjectTitle.status()).toBe(422);

    const project = await createProject(request, uniqueTitle('e2e-api'));
    const projectId = project.id;
    expect(projectId).toBeGreaterThan(0);
    expect(project.selected_mode).toBe('audiobook');

    const invalidModeResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'invalid-mode' },
    });
    expect(invalidModeResponse.status()).toBe(422);

    const modeResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeResponse.status()).toBe(200);
    const modePayload = (await modeResponse.json()) as {
      previous_mode: string;
      selected_mode: string;
      selected_modes: string[];
    };
    expect(modePayload.selected_mode).toBe('author');
    expect(modePayload.previous_mode).toBe('audiobook');
    expect(modePayload.selected_modes).toContain('author');

    const invalidTxtResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'sample.doc',
          mimeType: 'application/msword',
          buffer: Buffer.from('Not a text upload'),
        },
      },
    });
    expect(invalidTxtResponse.status()).toBe(400);

    const txtResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtResponse.status()).toBe(200);
    const txtPayload = (await txtResponse.json()) as { chapter_count: number };
    expect(txtPayload.chapter_count).toBeGreaterThan(0);

    const markdownResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/markdown`, {
      multipart: {
        file: {
          name: 'sample.md',
          mimeType: 'text/markdown',
          buffer: Buffer.from('# Chapter 1\nA quick markdown chapter.\n# Chapter 2\nAnother short chapter.'),
        },
      },
    });
    expect(markdownResponse.status()).toBe(200);
    const markdownPayload = (await markdownResponse.json()) as { chapter_count: number };
    expect(markdownPayload.chapter_count).toBeGreaterThanOrEqual(1);

    const chapterDirResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/chapters-dir`, {
      multipart: {
        files: createReadStream(fixtureNovelPath),
      },
    });
    expect(chapterDirResponse.status()).toBe(200);
    const chapterDirPayload = (await chapterDirResponse.json()) as { chapter_count: number };
    expect(chapterDirPayload.chapter_count).toBeGreaterThan(0);

    const appendResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/append-chapter`, {
      multipart: {
        file: {
          name: 'append-chapter.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 3\nThis is appended chapter three content.'),
        },
      },
    });
    expect(appendResponse.status()).toBe(200);
    const appendPayload = (await appendResponse.json()) as { chapter_count: number };
    expect(appendPayload.chapter_count).toBeGreaterThanOrEqual(chapterDirPayload.chapter_count);

    const overlappingAppendResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/append-chapter`, {
      multipart: {
        file: {
          name: 'append-chapter.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 3\nThis is appended chapter three content.'),
        },
      },
    });
    expect(overlappingAppendResponse.status()).toBe(409);

    const invalidMarkdownResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/markdown`, {
      multipart: {
        file: {
          name: 'bad.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('bad extension'),
        },
      },
    });
    expect(invalidMarkdownResponse.status()).toBe(400);

    const epubResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/epub`, {
      multipart: {
        file: {
          name: 'sample.epub',
          mimeType: 'application/epub+zip',
          buffer: Buffer.from('not-a-real-epub'),
        },
      },
    });
    expect([400, 501]).toContain(epubResponse.status());

    const importCharactersResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/import`, {
      multipart: {
        file: createReadStream(fixtureCharactersPath),
      },
    });
    expect(importCharactersResponse.status()).toBe(200);
    const importPayload = (await importCharactersResponse.json()) as { imported_count: number };
    expect(importPayload.imported_count).toBeGreaterThan(0);

    const listCharactersResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/characters`);
    expect(listCharactersResponse.status()).toBe(200);
    const listPayload = (await listCharactersResponse.json()) as { characters: Array<{ name: string; aliases: string[] }> };
    expect(listPayload.characters.length).toBe(3);

    const lookupResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/lookup-alias`, {
      data: { alias: 'Ace' },
    });
    expect(lookupResponse.status()).toBe(200);
    const lookupPayload = (await lookupResponse.json()) as { alias: string; canonical_name: string | null; match_source: string };
    expect(lookupPayload.alias).toBe('Ace');
    expect(lookupPayload.match_source).toBe('conflict');

    const collisionsResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/characters/alias-collisions`);
    expect(collisionsResponse.status()).toBe(200);
    const collisionsPayload = (await collisionsResponse.json()) as { collisions: Array<{ alias: string }> };
    expect(collisionsPayload.collisions.length).toBeGreaterThan(0);

    const extractResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/extract`);
    expect(extractResponse.status()).toBe(200);
    const extractPayload = (await extractResponse.json()) as { candidate_count: number; candidates: unknown[]; status: string };
    expect(extractPayload.status).toBe('complete');
    expect(extractPayload.candidate_count).toBeGreaterThanOrEqual(0);

    const mergeAutoResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/merged-candidates`, {
      data: { include_auto: true },
    });
    expect(mergeAutoResponse.status()).toBe(200);
    const mergeAutoPayload = (await mergeAutoResponse.json()) as { candidate_count: number };
    expect(mergeAutoPayload.candidate_count).toBeGreaterThanOrEqual(1);

    const mergedWithInvalidSourceUrl = await request.post(
      `${backendBaseUrl}/api/projects/${projectId}/characters/merged-candidates`,
      {
        data: {
          include_auto: false,
          source_url: 'not-a-valid-url',
          acknowledge_source_risk: true,
        },
      },
    );
    expect(mergedWithInvalidSourceUrl.status()).toBe(400);

    const inferResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/infer`);
    expect(inferResponse.status()).toBe(200);
    const inferPayload = (await inferResponse.json()) as { character_map_finalized: boolean };
    expect(inferPayload.character_map_finalized).toBe(false);

    const compareResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/characters/gender-comparison?include_only_conflicts=true`,
    );
    expect(compareResponse.status()).toBe(200);
    const comparePayload = (await compareResponse.json()) as { comparison_count: number };
    expect(comparePayload.comparison_count).toBeGreaterThanOrEqual(0);

    const upsertInvalidResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Bad',
            verbalized_form: 'Bad',
            gender: 'bad-gender',
            aliases: [],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(upsertInvalidResponse.status()).toBe(422);

    const upsertResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Alice',
            verbalized_form: 'Alice',
            gender: 'female',
            aliases: ['Al'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(upsertResponse.status()).toBe(200);
    const upsertPayload = (await upsertResponse.json()) as { characters: unknown[]; character_map_finalized: boolean };
    expect(upsertPayload.characters).toHaveLength(1);
    expect(upsertPayload.character_map_finalized).toBe(false);

    const runBlockedResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: false,
      },
    });
    expect(runBlockedResponse.status()).toBe(409);

    const finalizeResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/finalize`);
    expect(finalizeResponse.status()).toBe(200);
    const finalizePayload = (await finalizeResponse.json()) as { character_map_finalized: boolean };
    expect(finalizePayload.character_map_finalized).toBe(true);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: false,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number; project_id: number; status: string; segment_count: number };
    expect(runPayload.status).toBe('completed');
    expect(runPayload.segment_count).toBeGreaterThan(0);
    expect(runPayload.project_id).toBe(projectId);

    const runId = runPayload.run_id;

    const runDetailResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${runId}`);
    expect(runDetailResponse.status()).toBe(200);
    const runDetailPayload = (await runDetailResponse.json()) as { status: string; config: Record<string, unknown> };
    expect(runDetailPayload.status).toBe('completed');
    expect(runDetailPayload.config.mode).toBe('author');

    const analyticsResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/character-analytics`,
    );
    expect(analyticsResponse.status()).toBe(200);
    const analyticsPayload = (await analyticsResponse.json()) as {
      project_id: number;
      run_id: number;
      character_mentions_by_chapter: unknown[];
      character_mentions_per_1000_words: Record<string, number>;
    };
    expect(analyticsPayload.project_id).toBe(projectId);
    expect(analyticsPayload.run_id).toBe(runId);
    expect(Array.isArray(analyticsPayload.character_mentions_by_chapter)).toBe(true);
    expect(typeof analyticsPayload.character_mentions_per_1000_words).toBe('object');

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runId}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as { project_id: number; run_id: number; status: string; segments: unknown[] };
    expect(exportPayload.project_id).toBe(projectId);
    expect(exportPayload.run_id).toBe(runId);
    expect(Array.isArray(exportPayload.segments)).toBe(true);
    expect(exportPayload.segments.every((segment) => Object.hasOwn(segment as Record<string, unknown>, 'speaker_id'))).toBe(true);
    expect(
      exportPayload.segments.every(
        (segment) =>
          typeof (segment as Record<string, unknown>).confidence === 'object' &&
          Object.hasOwn(segment as Record<string, unknown>, 'confidence') &&
          Object.hasOwn((segment as Record<string, unknown>).confidence as Record<string, unknown>, 'speaker'),
      ),
    ).toBe(true);
    expect(
      exportPayload.segments.every(
        (segment) =>
          Object.hasOwn(segment as Record<string, unknown>, 'emotion_primary_label') &&
          Object.hasOwn(segment as Record<string, unknown>, 'emotion_secondary_label') &&
          Object.hasOwn((segment as Record<string, unknown>).confidence as Record<string, unknown>, 'emotion'),
      ),
    ).toBe(true);
    expect(
      exportPayload.segments.every((segment) =>
        Object.hasOwn(segment as Record<string, unknown>, 'tension_contribution'),
      ),
    ).toBe(true);
    expect(
      exportPayload.segments.every((segment) =>
        Object.hasOwn(segment as Record<string, unknown>, 'dominance_contribution'),
      ),
    ).toBe(true);

    const pronunciationScopes: Array<[string, string, string, string]> = [
      ['global', 'global', 'Nimble', 'Nim-ble'],
      ['places', 'place', 'Atlantis', 'At-Lan-tis'],
      ['artifacts', 'artifact', 'Aegis', 'EE-gis'],
      ['invented', 'invented', 'Avernus', 'Ah-vernus'],
    ];

    for (const [routeScope, responseScope, term, verbalizedForm] of pronunciationScopes) {
      const putResponse = await request.put(
        `${backendBaseUrl}/api/projects/${projectId}/pronunciation-dictionary/${routeScope}`,
        {
          data: {
            entries: [
              {
                term,
                verbalized_form: verbalizedForm,
                source: 'user',
                confidence: 1,
              },
            ],
          },
        },
      );
      expect(putResponse.status()).toBe(200);

      const getResponse = await request.get(
        `${backendBaseUrl}/api/projects/${projectId}/pronunciation-dictionary/${routeScope}`,
      );
      expect(getResponse.status()).toBe(200);
      const getPayload = (await getResponse.json()) as { scope: string; entries: Array<{ term: string }> };
      expect(getPayload.scope).toBe(responseScope);
      expect(
        getPayload.entries.some((entry) => entry.term === term),
      ).toBeTruthy();
    }

    const characterDictPut = await request.put(
      `${backendBaseUrl}/api/projects/${projectId}/pronunciation-dictionary/character/Alice`,
      {
        data: {
          entries: [
            {
              term: 'Alice',
              verbalized_form: 'Al-iss',
              source: 'user',
              confidence: 1,
            },
          ],
        },
      },
    );
    expect(characterDictPut.status()).toBe(200);
    const characterDictGet = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/pronunciation-dictionary/character/Alice`,
    );
    expect(characterDictGet.status()).toBe(200);

    const invalidDictionaryRequest = await request.post(
      `${backendBaseUrl}/api/projects/${projectId}/pronunciation-dictionary/preview`,
      {
        data: {
          text: 'No active scopes should fail this request.',
          include_global_scope: false,
          include_character_scope: false,
          include_place_scope: false,
          include_artifact_scope: false,
          include_invented_scope: false,
        },
      },
    );
    expect(invalidDictionaryRequest.status()).toBe(400);

    const previewResponse = await request.post(
      `${backendBaseUrl}/api/projects/${projectId}/pronunciation-dictionary/preview`,
      {
        data: {
          text: 'Nimble and Atlantis meet Alice in Aegis and Avernus.',
          include_global_scope: true,
          include_character_scope: true,
          include_place_scope: true,
          include_artifact_scope: true,
          include_invented_scope: true,
          character_name: 'Alice',
          match_whole_words: true,
          case_sensitive: true,
          alias_aware: true,
        },
      },
    );
    expect(previewResponse.status()).toBe(200);
    const previewPayload = (await previewResponse.json()) as {
      project_id: number;
      before: string;
      after: string;
      replacements: Array<{ term: string; count: number; scope: string; verbalized_form: string }>;
      included_scopes: string[];
    };
    expect(previewPayload.project_id).toBe(projectId);
    expect(previewPayload.replacements.length).toBeGreaterThan(0);
    expect(previewPayload.after).toContain('Nim-ble');
    expect(previewPayload.included_scopes).toEqual(
      expect.arrayContaining(['global', 'character', 'place', 'artifact', 'invented']),
    );

    const invalidVoicesResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/voices`, {
      data: {
        narrator_voice: '',
        male_default_voice: 'male',
        female_default_voice: 'female',
      },
    });
    expect(invalidVoicesResponse.status()).toBe(422);

    const voicesResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/voices`, {
      data: {
        narrator_voice: 'narrator_default',
        male_default_voice: 'male_default',
        female_default_voice: 'female_default',
        neutral_default_voice: 'neutral_default',
        unknown_default_voice: 'unknown_default',
      },
    });
    expect(voicesResponse.status()).toBe(200);
    const voicesPayload = (await voicesResponse.json()) as { voice_config: Record<string, string> };
    expect(voicesPayload.voice_config).toHaveProperty('narrator_voice', 'narrator_default');
    expect(voicesPayload.voice_config).toHaveProperty('male_default_voice', 'male_default');

    const scrapeRejectedResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/scrape`, {
      data: {
        source_url: 'https://example.com',
        acknowledge_source_risk: false,
      },
    });
    expect(scrapeRejectedResponse.status()).toBe(400);

    const scrapeRejectedNoScheme = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/scrape`, {
      data: {
        source_url: 'example.com',
        acknowledge_source_risk: true,
      },
    });
    expect(scrapeRejectedNoScheme.status()).toBe(400);
  });

  test('frontend route actions hit the live backend and keep state aligned end-to-end', async ({ page, request }) => {
    await page.goto('/projects/new');
    const title = uniqueTitle('e2e-ui');

    await page.getByTestId('project-title-input').fill(title);
    await page.getByTestId('create-project-button').click();
    await expect(page.getByTestId('project-created-state')).toContainText('Current project ID:');

    await page.getByTestId('txt-upload-input').setInputFiles(fixtureNovelPath);
    await page.getByTestId('upload-txt-button').click();
    await expect(page.getByTestId('chapter-count-state')).toContainText(/Detected chapters: \d+/);

    const stateAfterIngest = await readWorkspaceState(page);
    expect(stateAfterIngest?.projectId).toBeGreaterThan(0);
    expect(stateAfterIngest?.chapterCount).toBeGreaterThan(0);
    const projectId = stateAfterIngest?.projectId as number;

    await page.getByRole('button', { name: 'Continue to Mode Selection' }).click();
    await expect(page).toHaveURL(`/projects/${projectId}/mode`);
    await expect(page.getByTestId('mode-select')).toHaveValue('audiobook');
    await page.getByTestId('mode-select').selectOption('author');
    await expect(page.getByTestId('mode-required-hint')).not.toBeVisible();
    await page.getByTestId('mode-continue-button').click();

    await expect(page).toHaveURL(`/projects/${projectId}/characters`);
    await expect(page.getByRole('heading', { name: 'Character Map' })).toBeVisible();
    await page.getByTestId('character-file-input').setInputFiles(fixtureCharactersPath);
    await page.getByTestId('character-import-button').click();
    await expect(page.getByTestId('character-import-state')).toContainText('Imported rows: 3');

    await page.locator('button', { hasText: 'Save Character Map' }).click();
    await page.getByRole('button', { name: 'Finalize Character Map' }).click();
    await expect(page.getByRole('button', { name: 'Character Map Finalized' })).toBeVisible();

    await page.getByRole('button', { name: 'Continue to Pipeline Setup' }).click();
    await expect(page).toHaveURL(`/projects/${projectId}/pipeline-setup`);

    await page.getByRole('button', { name: 'Save Voice Config' }).click();
    await page.getByTestId('run-pipeline-button').click();

    await expect(page).toHaveURL(`/projects/${projectId}/run-monitor`);
    const stateAfterRun = await readWorkspaceState(page);
    expect(stateAfterRun?.runId).toBeGreaterThan(0);

    const runResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${stateAfterRun?.runId}`);
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { status: string };
    expect(runPayload.status).toBe('completed');

    const exportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/exports/${stateAfterRun?.runId}.json`,
    );
    expect(exportResponse.status()).toBe(200);

    await expect(page.getByRole('button', { name: 'Continue to Export' })).toBeVisible();
    await page.getByRole('button', { name: 'Continue to Export' }).click();
    await expect(page).toHaveURL(`/projects/${projectId}/export`);
    await expect(page.getByRole('button', { name: /Download JSON/i })).toBeEnabled();
  });

  test('speaker attribution fields include speaker_id and speaker confidence in exports', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-speaker-attribution'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'speaker-attribution.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\n"Come closer," Alice said.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const upsertResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Alice',
            verbalized_form: 'Alice',
            gender: 'female',
            aliases: ['Al'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(upsertResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };
    expect(runPayload.run_id).toBeGreaterThan(0);

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        speaker: string;
        speaker_id: number | null;
        confidence: { speaker: number; emotion?: number };
      }>;
    };

    const resolvedSegment = exportPayload.segments.find((segment) => segment.speaker.toLowerCase() === 'alice');
    expect(resolvedSegment).toBeDefined();
    expect(typeof resolvedSegment?.speaker_id).toBe('number');
    expect(resolvedSegment?.speaker_id).toBeGreaterThan(0);
    expect(typeof resolvedSegment?.confidence.speaker).toBe('number');
    expect(resolvedSegment?.confidence.speaker).toBeGreaterThan(0.0);
  });

  test('export includes emotion labels and valence-intensity details for real run', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-emotion-tags'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'emotion-tags.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nCold rain fell on a ruined gate.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        emotion_valence: number;
        emotion_intensity: number;
        emotion_primary_label: string;
        emotion_secondary_label: string;
        confidence: { emotion?: number };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const segment = exportPayload.segments[0];
    expect(typeof segment.emotion_valence).toBe('number');
    expect(typeof segment.emotion_intensity).toBe('number');
    expect(Math.abs(segment.emotion_intensity)).toBeGreaterThanOrEqual(0);
    expect(segment.emotion_primary_label).toMatch(/(positive|negative|neutral)/);
    expect(segment.emotion_secondary_label).toBeTruthy();
    expect(typeof segment.confidence.emotion).toBe('number');
  });

  test('export includes per-segment tension contribution details', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-tension-tags'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'tension-tags.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nHe grabbed a knife and dashed toward the open gate.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{ tension_contribution?: { value: number; level: string } }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.tension_contribution).toBeDefined();
    expect(typeof firstSegment.tension_contribution).toBe('object');
    expect(typeof firstSegment.tension_contribution?.value).toBe('number');
    expect(typeof firstSegment.tension_contribution?.level).toBe('string');
    expect(typeof firstSegment.tension_contribution?.confidence).toBe('number');
    expect(firstSegment.tension_contribution?.value).toBeGreaterThan(0);
    expect(firstSegment.tension_contribution?.value).toBeLessThanOrEqual(1);
    expect(['calm', 'low', 'moderate', 'high']).toContain(firstSegment.tension_contribution?.level);
  });

  test('export includes per-segment emotion shift details', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-emotion-shift'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'emotion-shift-tags.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nThe moonlight was warm, but fear and despair arrived.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 160,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        emotion_shift?: {
          has_shift: boolean;
          from: { label: string; valence: number; start_char: number; end_char: number } | null;
          to: { label: string; valence: number; start_char: number; end_char: number } | null;
          confidence: number;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.emotion_shift).toBeDefined();
    expect(typeof firstSegment.emotion_shift?.has_shift).toBe('boolean');
    expect(typeof firstSegment.emotion_shift?.confidence).toBe('number');
    if (firstSegment.emotion_shift?.has_shift) {
      expect(firstSegment.emotion_shift?.from).toBeDefined();
      expect(firstSegment.emotion_shift?.to).toBeDefined();
      expect(firstSegment.emotion_shift?.from?.label).toBeTruthy();
      expect(firstSegment.emotion_shift?.to?.label).toBeTruthy();
      expect(firstSegment.emotion_shift?.from?.label).not.toBe(firstSegment.emotion_shift?.to?.label);
    }
  });

  test('export includes narration/internal thought shift details', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-narration-internal-shift'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'narration-internal-thought-shift.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nShe thought the rain would stop, but the sirens kept wailing.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 180,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        narration_internal_thought_shift?: {
          has_shift: boolean;
          from: { type: string; text: string; start_char: number; end_char: number } | null;
          to: { type: string; text: string; start_char: number; end_char: number } | null;
          confidence: number;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.narration_internal_thought_shift).toBeDefined();
    expect(typeof firstSegment.narration_internal_thought_shift?.has_shift).toBe('boolean');
    expect(typeof firstSegment.narration_internal_thought_shift?.confidence).toBe('number');
    if (firstSegment.narration_internal_thought_shift?.has_shift) {
      expect(firstSegment.narration_internal_thought_shift?.from).toBeDefined();
      expect(firstSegment.narration_internal_thought_shift?.to).toBeDefined();
      expect(firstSegment.narration_internal_thought_shift?.from?.type).toBeTruthy();
      expect(firstSegment.narration_internal_thought_shift?.to?.type).toBeTruthy();
      expect(firstSegment.narration_internal_thought_shift?.from?.type)
        .not.toBe(firstSegment.narration_internal_thought_shift?.to?.type);
    }
  });

  test('export includes internal<->external speech shift details', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-internal-external-shift'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'internal-external-shift.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nShe thought he would answer. "We should go now."'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 200,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        internal_external_speech_shift?: {
          has_shift: boolean;
          from: { type: string; text: string; start_char: number; end_char: number } | null;
          to: { type: string; text: string; start_char: number; end_char: number } | null;
          confidence: number;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.internal_external_speech_shift).toBeDefined();
    expect(typeof firstSegment.internal_external_speech_shift?.has_shift).toBe('boolean');
    expect(typeof firstSegment.internal_external_speech_shift?.confidence).toBe('number');
    if (firstSegment.internal_external_speech_shift?.has_shift) {
      expect(firstSegment.internal_external_speech_shift?.from).toBeDefined();
      expect(firstSegment.internal_external_speech_shift?.to).toBeDefined();
      expect(firstSegment.internal_external_speech_shift?.from?.type).toBeTruthy();
      expect(firstSegment.internal_external_speech_shift?.to?.type).toBeTruthy();
      expect(firstSegment.internal_external_speech_shift?.from?.type)
        .not.toBe(firstSegment.internal_external_speech_shift?.to?.type);
    }
  });

  test('export includes sub-segment boundary records for detected shifts', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-sub-segment-boundaries'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'sub-segment-boundaries.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nShe thought he would answer. "No," he said. Great, but the outcome was terrible.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 220,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        sub_segment_boundaries?: Array<{
          shift_type: string;
          boundary_start_char: number;
          boundary_end_char: number;
          from_label: string | null;
          to_label: string | null;
          from_text: string;
          to_text: string;
          confidence: number;
        }>;
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.sub_segment_boundaries).toBeDefined();
    expect(Array.isArray(firstSegment.sub_segment_boundaries)).toBe(true);
    if ((firstSegment.sub_segment_boundaries ?? []).length > 0) {
      const boundary = firstSegment.sub_segment_boundaries?.[0];
      expect(boundary?.shift_type).toBeTruthy();
      expect(typeof boundary?.boundary_start_char).toBe('number');
      expect(typeof boundary?.boundary_end_char).toBe('number');
      expect(typeof boundary?.from_label).toBe('string');
      expect(typeof boundary?.to_label).toBe('string');
      expect(boundary?.from_text).toBeTruthy();
      expect(boundary?.to_text).toBeTruthy();
    }
  });

  test('export includes parent segment summary tag', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-summary-tag'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'segment-summary.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nGreat, but the outcome was terrible.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 160,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        type?: string;
        summary_tag?: {
          tag_type: string;
          dominant_tone: string;
          dominant_state: string;
          dominant_agent: string;
          confidence: number;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.summary_tag).toBeDefined();
    expect(firstSegment.summary_tag?.tag_type).toBe('segment_summary');
    expect(firstSegment.summary_tag?.dominant_tone).toBe('dark_irony');
    expect(firstSegment.summary_tag?.dominant_state).toBe(firstSegment.type);
    expect(typeof firstSegment.summary_tag?.confidence).toBe('number');
  });

  test('export includes tone reversal / dark irony marker details', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-tone-reversal'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'tone-reversal.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nGreat, but the outcome was terrible.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 180,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        tone_reversal?: {
          has_tone_reversal: boolean;
          tone: string | null;
          from: { label: string; valence: number; start_char: number; end_char: number } | null;
          to: { label: string; valence: number; start_char: number; end_char: number } | null;
          confidence: number;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.tone_reversal).toBeDefined();
    expect(typeof firstSegment.tone_reversal?.has_tone_reversal).toBe('boolean');
    expect(typeof firstSegment.tone_reversal?.confidence).toBe('number');
    if (firstSegment.tone_reversal?.has_tone_reversal) {
      expect(firstSegment.tone_reversal?.tone).toBe('dark_irony');
      expect(firstSegment.tone_reversal?.from).toBeDefined();
      expect(firstSegment.tone_reversal?.to).toBeDefined();
      expect(firstSegment.tone_reversal?.from?.label).toBeTruthy();
      expect(firstSegment.tone_reversal?.to?.label).toBeTruthy();
      expect(firstSegment.tone_reversal?.from?.label)
        .not.toBe(firstSegment.tone_reversal?.to?.label);
    }
  });

  test('export includes per-segment dominance contribution details', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-dominance-tags'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'dominance-tags.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nAlice said, "Move now."'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{ dominance_contribution?: { value: number; level: string; dominant_agent: string; evidence: Record<string, unknown> } }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.dominance_contribution).toBeDefined();
    expect(typeof firstSegment.dominance_contribution).toBe('object');
    expect(typeof firstSegment.dominance_contribution?.value).toBe('number');
    expect(typeof firstSegment.dominance_contribution?.level).toBe('string');
    expect(typeof firstSegment.dominance_contribution?.dominant_agent).toBe('string');
    expect(typeof firstSegment.dominance_contribution?.confidence).toBe('number');
    expect(firstSegment.dominance_contribution?.dominant_agent.length).toBeGreaterThan(0);
    expect(typeof firstSegment.dominance_contribution?.evidence).toBe('object');
    expect(firstSegment.dominance_contribution?.value).toBeGreaterThanOrEqual(0);
    expect(firstSegment.dominance_contribution?.value).toBeLessThanOrEqual(1);
    expect(['dominant', 'strong', 'moderate', 'low']).toContain(firstSegment.dominance_contribution?.level);
  });

  test('export includes structural confidence score on each segment', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-structure-confidence'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'structure-confident.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\n"Move quickly," Alice said. The room grew quieter.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 180,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as {
      segments: Array<{
        type_confidence?: number;
        confidence?: {
          type?: number;
          tension?: number;
          dominance?: number;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(typeof firstSegment.type_confidence).toBe('number');
    expect(firstSegment.type_confidence).toBeGreaterThan(0);
    expect(typeof firstSegment.confidence?.type).toBe('number');
    expect(typeof firstSegment.confidence?.tension).toBe('number');
    expect(typeof firstSegment.confidence?.dominance).toBe('number');
  });
});
