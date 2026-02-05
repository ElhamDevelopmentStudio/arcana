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
  llm_enabled: boolean;
};

type ModeCatalogResponse = {
  modes: string[];
  default_mode: string;
  persisted_in: string[];
  mode_profiles: Record<
    string,
    {
      max_segment_chars: number;
      llm_enabled: boolean;
      provider_name: string;
      export_formats: string[];
      export_chunk_size: number;
    }
  >;
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
    expect(modesPayload.mode_profiles.audiobook.export_formats).toEqual(
      expect.arrayContaining(['json', 'csv', 'time_series_json', 'graph_json']),
    );
    expect(modesPayload.mode_profiles.audiobook.export_chunk_size).toBeGreaterThan(0);

    const missingProjectTitle = await request.post(`${backendBaseUrl}/api/projects`, { data: { title: '' } });
    expect(missingProjectTitle.status()).toBe(422);

    const project = await createProject(request, uniqueTitle('e2e-api'));
    const projectId = project.id;
    expect(projectId).toBeGreaterThan(0);
    expect(project.selected_mode).toBe('audiobook');
    expect(project.llm_enabled).toBe(false);

    const projectLlmGetResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/llm`);
    expect(projectLlmGetResponse.status()).toBe(200);
    const projectLlmGetPayload = (await projectLlmGetResponse.json()) as { project_id: number; llm_enabled: boolean };
    expect(projectLlmGetPayload.project_id).toBe(projectId);
    expect(projectLlmGetPayload.llm_enabled).toBe(false);

    const projectLlmPutResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/llm`, {
      data: {
        llm_enabled: true,
      },
    });
    expect(projectLlmPutResponse.status()).toBe(200);
    const projectLlmPutPayload = (await projectLlmPutResponse.json()) as { project_id: number; llm_enabled: boolean };
    expect(projectLlmPutPayload.project_id).toBe(projectId);
    expect(projectLlmPutPayload.llm_enabled).toBe(true);

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

    const shadowSlaveProject = await createProject(request, uniqueTitle('e2e-acc001-shadow-slave'));
    const shadowSlaveIngestResponse = await request.post(
      `${backendBaseUrl}/api/projects/${shadowSlaveProject.id}/ingest/txt`,
      {
        multipart: {
          file: {
            name: 'shadow-slave-corpus.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from(
              'Shadow Slave\n\n'
                + 'Chapter 1\n'
                + 'Sunny stood at the edge of the ruined courtyard while rain struck old stone.\n\n'
                + 'Chapter 2\n'
                + 'Nephis watched the horizon and counted each distant flare in the night.\n\n'
                + 'Chapter 3\n'
                + 'The gate opened and their steps echoed through the drowned corridor.',
            ),
          },
        },
      },
    );
    expect(shadowSlaveIngestResponse.status()).toBe(200);
    const shadowSlaveIngestPayload = (await shadowSlaveIngestResponse.json()) as { chapter_count: number };
    expect(shadowSlaveIngestPayload.chapter_count).toBe(3);

    const shadowSlaveRunResponse = await request.post(`${backendBaseUrl}/api/projects/${shadowSlaveProject.id}/runs`, {
      data: {
        mode: 'audiobook',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 2,
        allow_unfinalized_character_map: true,
      },
    });
    expect(shadowSlaveRunResponse.status()).toBe(200);
    const shadowSlaveRunPayload = (await shadowSlaveRunResponse.json()) as { run_id: number };

    const shadowSlaveExportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${shadowSlaveProject.id}/exports/${shadowSlaveRunPayload.run_id}.json`,
    );
    expect(shadowSlaveExportResponse.status()).toBe(200);
    const shadowSlaveExportPayload = (await shadowSlaveExportResponse.json()) as {
      status: string;
      segments: Array<{ chapter_id: number | string }>;
    };
    expect(shadowSlaveExportPayload.status).toBe('completed');
    const shadowSlaveChapterIds = Array.from(
      new Set(shadowSlaveExportPayload.segments.map((segment) => Number(segment.chapter_id))),
    ).sort((a, b) => a - b);
    expect(shadowSlaveChapterIds).toEqual([1, 2, 3]);

    const phoneticProject = await createProject(request, uniqueTitle('e2e-acc004-phonetic-export'));
    const phoneticIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${phoneticProject.id}/ingest/txt`, {
      multipart: {
        file: {
          name: 'phonetic-export-source.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(
            'Chapter 1\nThe Aegis stood above the tower while the crew watched in silence.',
          ),
        },
      },
    });
    expect(phoneticIngestResponse.status()).toBe(200);

    const phoneticDictionaryResponse = await request.put(
      `${backendBaseUrl}/api/projects/${phoneticProject.id}/pronunciation-dictionary/global`,
      {
        data: {
          entries: [{ term: 'Aegis', verbalized_form: 'EE-gis', confidence: 1 }],
        },
      },
    );
    expect(phoneticDictionaryResponse.status()).toBe(200);

    const phoneticRunResponse = await request.post(`${backendBaseUrl}/api/projects/${phoneticProject.id}/runs`, {
      data: {
        mode: 'audiobook',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 2,
        allow_unfinalized_character_map: true,
      },
    });
    expect(phoneticRunResponse.status()).toBe(200);
    const phoneticRunPayload = (await phoneticRunResponse.json()) as { run_id: number };

    const phoneticExportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${phoneticProject.id}/exports/${phoneticRunPayload.run_id}.json`,
    );
    expect(phoneticExportResponse.status()).toBe(200);
    const phoneticExportPayload = (await phoneticExportResponse.json()) as {
      status: string;
      segments: Array<{ phonetic_text: string; normalized_text: string }>;
    };
    expect(phoneticExportPayload.status).toBe('completed');
    expect(
      phoneticExportPayload.segments.every((segment) => typeof segment.phonetic_text === 'string' && segment.phonetic_text.length > 0),
    ).toBe(true);
    expect(
      phoneticExportPayload.segments.some((segment) => segment.phonetic_text.includes('EE-gis')),
    ).toBe(true);
    expect(
      phoneticExportPayload.segments.some(
        (segment) => segment.normalized_text.includes('Aegis') && segment.phonetic_text.includes('EE-gis'),
      ),
    ).toBe(true);

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
    const comparePayload = (await compareResponse.json()) as {
      comparison_count: number;
      contradiction_count: number;
      comparisons: Array<{
        name: string;
        manual_gender: string;
        inferred_gender: string;
        contradiction_severity: number;
        is_contradiction: boolean;
        requires_review: boolean;
      }>;
    };
    expect(comparePayload.comparison_count).toBeGreaterThanOrEqual(0);
    expect(comparePayload.contradiction_count).toBeGreaterThanOrEqual(0);
    expect(Array.isArray(comparePayload.comparisons)).toBe(true);
    for (const entry of comparePayload.comparisons) {
      expect(typeof entry.name).toBe('string');
      expect(typeof entry.manual_gender).toBe('string');
      expect(typeof entry.inferred_gender).toBe('string');
      expect(entry.contradiction_severity).toBeGreaterThanOrEqual(0);
      expect(entry.contradiction_severity).toBeLessThanOrEqual(1);
      expect(typeof entry.is_contradiction).toBe('boolean');
      expect(typeof entry.requires_review).toBe('boolean');
    }

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

    const refreshedCharacterMapResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/characters`);
    expect(refreshedCharacterMapResponse.status()).toBe(200);
    const refreshedCharacterMapPayload = (await refreshedCharacterMapResponse.json()) as {
      character_map_finalized: boolean;
      characters: Array<{ name: string; verbalized_form: string; gender: string; aliases: string[] }>;
    };
    expect(refreshedCharacterMapPayload.character_map_finalized).toBe(false);
    const refreshedAliceRow = refreshedCharacterMapPayload.characters.find((entry) => entry.name === 'Alice');
    expect(refreshedAliceRow?.aliases).toEqual(expect.arrayContaining(['Al']));
    expect(refreshedAliceRow?.verbalized_form).toBe('Alice');
    expect(refreshedAliceRow?.gender).toBe('female');

    const invalidSegmentationTargetResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 256,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(invalidSegmentationTargetResponse.status()).toBe(422);
    const invalidSegmentationTargetPayload = (await invalidSegmentationTargetResponse.json()) as {
      detail: string;
      field_errors?: Array<{ field?: string; message?: string }>;
    };
    expect(invalidSegmentationTargetPayload.detail).toBe('Run configuration validation failed.');
    expect(
      invalidSegmentationTargetPayload.field_errors?.some(
        (fieldError) =>
          String(fieldError.field ?? '').startsWith('max_segment_chars') &&
          String(fieldError.message ?? '').includes('less than or equal to 255'),
      ),
    ).toBeTruthy();

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

    const projectInheritedRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(projectInheritedRunResponse.status()).toBe(200);
    const projectInheritedRunPayload = (await projectInheritedRunResponse.json()) as {
      run_id: number;
    };
    const projectInheritedRunDetailResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${projectInheritedRunPayload.run_id}`,
    );
    expect(projectInheritedRunDetailResponse.status()).toBe(200);
    const projectInheritedRunDetail = (await projectInheritedRunDetailResponse.json()) as {
      config: { llm_enabled: boolean };
    };
    expect(projectInheritedRunDetail.config.llm_enabled).toBe(true);

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
    const runDetailPayload = (await runDetailResponse.json()) as {
      status: string;
      config: Record<string, unknown>;
      changelog_entries: Array<{ event_type: string }>;
    };
    expect(['queued', 'running', 'completed', 'failed', 'cancelled']).toContain(runDetailPayload.status);
    expect(runDetailPayload.status).toBe('completed');
    const changelogEventTypes = runDetailPayload.changelog_entries.map((entry) => entry.event_type);
    expect(changelogEventTypes).toContain('pipeline_execution_queued');
    expect(changelogEventTypes).toContain('pipeline_execution_started');
    expect(changelogEventTypes).toContain('pipeline_completed');
    expect(changelogEventTypes.indexOf('pipeline_execution_queued')).toBeLessThan(
      changelogEventTypes.indexOf('pipeline_execution_started'),
    );
    expect(runDetailPayload.config.mode).toBe('author');
    expect(runDetailPayload.config.config_schema_version).toBe('1.0.0');
    const normalizationReport = runDetailPayload.config.normalization_report as {
      source: string;
      counts: {
        chapters_detected: number;
      };
      lossy_transform_flags: Record<string, unknown>;
    };
    expect(typeof normalizationReport.source).toBe('string');
    expect(normalizationReport.counts.chapters_detected).toBeGreaterThanOrEqual(1);
    expect(typeof normalizationReport.lossy_transform_flags).toBe('object');
    expect(typeof runDetailPayload.config.configuration_snapshot_id).toBe('string');
    expect(String(runDetailPayload.config.configuration_snapshot_id)).toMatch(new RegExp(`^run-${runId}-config-\\d+$`));
    expect(typeof runDetailPayload.config.configuration_snapshot_version).toBe('number');
    expect(Number(runDetailPayload.config.configuration_snapshot_version)).toBeGreaterThanOrEqual(1);

    const runConfigPresetResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/config-preset`,
    );
    expect(runConfigPresetResponse.status()).toBe(200);
    const runConfigPresetPayload = (await runConfigPresetResponse.json()) as {
      project_id: number;
      run_id: number;
      preset_schema_version: string;
      generated_at: string;
      run_config: Record<string, unknown>;
    };
    expect(runConfigPresetPayload.project_id).toBe(projectId);
    expect(runConfigPresetPayload.run_id).toBe(runId);
    expect(runConfigPresetPayload.preset_schema_version).toBe('1.0.0');
    expect(typeof runConfigPresetPayload.generated_at).toBe('string');
    expect(runConfigPresetPayload.run_config.mode).toBe('author');
    expect(Object.hasOwn(runConfigPresetPayload.run_config, 'configuration_snapshot_id')).toBe(false);
    expect(Object.hasOwn(runConfigPresetPayload.run_config, 'configuration_snapshot_version')).toBe(false);

    const runFromPresetResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        ...runConfigPresetPayload.run_config,
        config_schema_version: '0.9.0',
        legacy_profile_name: 'release-2025',
      },
    });
    expect(runFromPresetResponse.status()).toBe(200);
    const runFromPresetPayload = (await runFromPresetResponse.json()) as { run_id: number };
    expect(runFromPresetPayload.run_id).toBeGreaterThan(0);

    const runWithFormatOverrideResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'academic',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: false,
        export_formats: [' json ', 'CSV', 'json'],
      },
    });
    expect(runWithFormatOverrideResponse.status()).toBe(200);
    const runWithFormatOverridePayload = (await runWithFormatOverrideResponse.json()) as {
      run_id: number;
    };
    const runWithFormatOverrideDetailResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runWithFormatOverridePayload.run_id}`,
    );
    expect(runWithFormatOverrideDetailResponse.status()).toBe(200);
    const runWithFormatOverrideDetail = (await runWithFormatOverrideDetailResponse.json()) as {
      config: { export_formats: string[] };
    };
    expect(runWithFormatOverrideDetail.config.export_formats).toEqual(['json', 'csv']);

    const runConfigDiffResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/config-diff`
      + `?base_run_id=${runId}&target_run_id=${runWithFormatOverridePayload.run_id}`,
    );
    expect(runConfigDiffResponse.status()).toBe(200);
    const runConfigDiffPayload = (await runConfigDiffResponse.json()) as {
      project_id: number;
      base_run_id: number;
      target_run_id: number;
      base_config_schema_version: string;
      target_config_schema_version: string;
      is_identical: boolean;
      changed_fields: Array<{ field: string; base_value: unknown; target_value: unknown }>;
      base_only_fields: string[];
      target_only_fields: string[];
    };
    expect(runConfigDiffPayload.project_id).toBe(projectId);
    expect(runConfigDiffPayload.base_run_id).toBe(runId);
    expect(runConfigDiffPayload.target_run_id).toBe(runWithFormatOverridePayload.run_id);
    expect(runConfigDiffPayload.base_config_schema_version).toBe('1.0.0');
    expect(runConfigDiffPayload.target_config_schema_version).toBe('1.0.0');
    expect(runConfigDiffPayload.is_identical).toBe(false);
    expect(runConfigDiffPayload.changed_fields.some((entry) => entry.field === 'mode')).toBe(true);
    expect(runConfigDiffPayload.changed_fields.some((entry) => entry.field === 'export_formats')).toBe(true);

    const deterministicRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: false,
        deterministic_mode: true,
        deterministic_seed: 2026,
        deterministic_model_identifier: 'openai/gpt-4o-mini',
        randomization_config: {
          seed: 2026,
          strategy: 'stable',
          shuffle_enabled: false,
        },
      },
    });
    expect(deterministicRunResponse.status()).toBe(200);
    const deterministicRunPayload = (await deterministicRunResponse.json()) as { run_id: number };
    const deterministicRunDetailResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${deterministicRunPayload.run_id}`,
    );
    expect(deterministicRunDetailResponse.status()).toBe(200);
    const deterministicRunDetail = (await deterministicRunDetailResponse.json()) as {
      config: {
        deterministic_mode: boolean;
        deterministic_seed: number;
        deterministic_model_identifier: string;
        randomization_config: {
          seed: number;
          strategy: string;
          shuffle_enabled: boolean;
        };
      };
    };
    expect(deterministicRunDetail.config.deterministic_mode).toBe(true);
    expect(deterministicRunDetail.config.deterministic_seed).toBe(2026);
    expect(deterministicRunDetail.config.deterministic_model_identifier).toBe('openai/gpt-4o-mini');
    expect(deterministicRunDetail.config.randomization_config).toEqual({
      seed: 2026,
      strategy: 'stable',
      shuffle_enabled: false,
    });

    const invalidExportFormatRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'academic',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: false,
        export_formats: ['invalid_format'],
      },
    });
    expect(invalidExportFormatRunResponse.status()).toBe(422);
    const invalidExportFormatRunPayload = (await invalidExportFormatRunResponse.json()) as {
      detail: string;
      field_errors: Array<{ field: string; message: string; code: string }>;
    };
    expect(invalidExportFormatRunPayload.detail).toBe('Run configuration validation failed.');
    expect(
      invalidExportFormatRunPayload.field_errors.some(
        (entry) =>
          entry.field.startsWith('export_formats')
          && entry.message.includes('one of: json, csv, time_series_json, graph_json'),
      ),
    ).toBe(true);

    const workspaceCreateResponse = await request.post(`${backendBaseUrl}/api/comparison-workspaces`, {
      data: { name: uniqueTitle('comparison-workspace') },
    });
    expect(workspaceCreateResponse.status()).toBe(201);
    const workspacePayload = (await workspaceCreateResponse.json()) as {
      workspace_id: number;
      run_count: number;
    };
    expect(workspacePayload.run_count).toBe(0);

    const addRunToWorkspaceResponse = await request.post(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/runs`,
      {
        data: {
          project_id: projectId,
          run_id: runId,
        },
      },
    );
    expect(addRunToWorkspaceResponse.status()).toBe(201);
    const workspaceAfterAddPayload = (await addRunToWorkspaceResponse.json()) as {
      run_count: number;
      runs: Array<{ run_id: number }>;
    };
    expect(workspaceAfterAddPayload.run_count).toBe(1);
    expect(workspaceAfterAddPayload.runs).toHaveLength(1);
    expect(workspaceAfterAddPayload.runs[0].run_id).toBe(runId);

    const getWorkspaceResponse = await request.get(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}`,
    );
    expect(getWorkspaceResponse.status()).toBe(200);
    const getWorkspacePayload = (await getWorkspaceResponse.json()) as { run_count: number; runs: unknown[] };
    expect(getWorkspacePayload.run_count).toBe(1);
    expect(Array.isArray(getWorkspacePayload.runs)).toBe(true);

    const alignedCurvesResponse = await request.get(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/aligned-curves`,
    );
    expect(alignedCurvesResponse.status()).toBe(200);
    const alignedCurvesPayload = (await alignedCurvesResponse.json()) as {
      workspace_id: number;
      run_count: number;
      aligned_points: number;
      metrics: Array<{ metric_id: string; points_per_run: Array<{ points: unknown[] }> }>;
    };
    expect(alignedCurvesPayload.workspace_id).toBe(workspacePayload.workspace_id);
    expect(alignedCurvesPayload.run_count).toBe(1);
    expect(alignedCurvesPayload.aligned_points).toBe(32);
    expect(
      alignedCurvesPayload.metrics.some((metric) => metric.metric_id === 'normalized_pacing_signature'),
    ).toBe(true);
    expect(alignedCurvesPayload.metrics.length).toBeGreaterThan(0);
    expect(alignedCurvesPayload.metrics.every((metric) => metric.points_per_run.length === 1)).toBe(true);
    expect(
      alignedCurvesPayload.metrics.every((metric) => metric.points_per_run[0].points.length === 32),
    ).toBe(true);

    const filteredCurvesResponse = await request.get(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/aligned-curves`
      + '?metrics=chapter_valence_mean,smoothed_tension_curve,normalized_pacing_signature&aligned_points=7',
    );
    expect(filteredCurvesResponse.status()).toBe(200);
    const filteredCurvesPayload = (await filteredCurvesResponse.json()) as {
      run_count: number;
      aligned_points: number;
      metrics: Array<{ metric_id: string; points_per_run: Array<{ points: unknown[] }> }>;
    };
    expect(filteredCurvesPayload.run_count).toBe(1);
    expect(filteredCurvesPayload.aligned_points).toBe(7);
    expect(filteredCurvesPayload.metrics).toHaveLength(3);
    expect(
      filteredCurvesPayload.metrics.every((metric) => metric.points_per_run.every((run) => run.points.length === 7)),
    ).toBe(true);
    expect(filteredCurvesPayload.metrics.map((metric) => metric.metric_id).sort()).toEqual(
      ['chapter_valence_mean', 'smoothed_tension_curve', 'normalized_pacing_signature'].sort(),
    );

    const invalidMetricResponse = await request.get(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/aligned-curves?metrics=bad_metric`,
    );
    expect(invalidMetricResponse.status()).toBe(422);

    const comparativeExportResponse = await request.get(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/exports/comparative-dataset.json`,
    );
    expect(comparativeExportResponse.status()).toBe(200);
    const comparativeExportPayload = (await comparativeExportResponse.json()) as {
      workspace_id: number;
      workspace_name: string;
      generated_at: string;
      run_count: number;
      aligned_points: number;
      metrics: Array<{ metric_id: string; points_per_run: Array<{ run_id: number; points: unknown[] }> }>;
      runs: Array<{
        run_id: number;
        project_id: number;
        project_title: string;
        status: string;
        segment_count: number;
        run_config_mode: string;
        academic_reports: Record<string, unknown>;
        comparative_run_metrics_snapshot: Record<string, unknown>;
        academic_export_manifest: Record<string, unknown>;
      }>;
    };
    expect(comparativeExportPayload.workspace_id).toBe(workspacePayload.workspace_id);
    expect(comparativeExportPayload.workspace_name).toBeTruthy();
    expect(comparativeExportPayload.generated_at).toBeTruthy();
    expect(comparativeExportPayload.run_count).toBe(1);
    expect(comparativeExportPayload.aligned_points).toBe(32);
    expect(comparativeExportPayload.metrics.length).toBeGreaterThan(0);
    expect(comparativeExportPayload.metrics.every((metric) => metric.points_per_run.length === 1)).toBe(true);
    expect(comparativeExportPayload.metrics.every((metric) => metric.points_per_run[0].points.length === 32)).toBe(true);
    expect(comparativeExportPayload.runs).toHaveLength(1);
    expect(comparativeExportPayload.runs[0].run_id).toBe(runId);
    expect(comparativeExportPayload.runs[0].academic_reports).toBeTruthy();
    expect(comparativeExportPayload.runs[0].comparative_run_metrics_snapshot).toBeTruthy();
    expect(comparativeExportPayload.runs[0].academic_export_manifest).toBeTruthy();

    const filteredComparativeExportResponse = await request.get(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/exports/comparative-dataset.json`
      + '?metrics=chapter_valence_mean,smoothed_tension_curve,normalized_pacing_signature&aligned_points=7',
    );
    expect(filteredComparativeExportResponse.status()).toBe(200);
    const filteredComparativeExportPayload = (await filteredComparativeExportResponse.json()) as {
      run_count: number;
      aligned_points: number;
      metrics: Array<{ metric_id: string }>;
    };
    expect(filteredComparativeExportPayload.run_count).toBe(1);
    expect(filteredComparativeExportPayload.aligned_points).toBe(7);
    expect(filteredComparativeExportPayload.metrics.map((metric) => metric.metric_id).sort()).toEqual(
      ['chapter_valence_mean', 'smoothed_tension_curve', 'normalized_pacing_signature'].sort(),
    );

    const invalidComparativeExportResponse = await request.get(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/exports/comparative-dataset.json?metrics=bad_metric`,
    );
    expect(invalidComparativeExportResponse.status()).toBe(422);

    const invalidRunAssignmentResponse = await request.post(
      `${backendBaseUrl}/api/comparison-workspaces/${workspacePayload.workspace_id}/runs`,
      {
        data: {
          project_id: projectId + 10_000,
          run_id: runId,
        },
      },
    );
    expect(invalidRunAssignmentResponse.status()).toBe(404);

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

    const audiobookPrepDashboardResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/audiobook-prep-dashboard`,
    );
    expect(audiobookPrepDashboardResponse.status()).toBe(200);
    const audiobookPrepDashboardPayload = (await audiobookPrepDashboardResponse.json()) as {
      schema_version: string;
      output_schema: string;
      output_format: string;
      output_id: string;
      output_name: string;
      project_id: number;
      run_id: number;
      run_status: string;
      generated_at: string;
      unresolved_speaker_count: number;
      unresolved_voice_mapping_count: number;
      low_confidence_region_count: number;
      export_readiness: {
        is_ready: boolean;
        blocking_reasons: string[];
        warning_reasons: string[];
      };
    };
    expect(audiobookPrepDashboardPayload.schema_version).toBe('1.0.0');
    expect(audiobookPrepDashboardPayload.output_schema).toBe('audiobook_prep_dashboard_json');
    expect(audiobookPrepDashboardPayload.output_format).toBe('json');
    expect(audiobookPrepDashboardPayload.output_id).toBe('AB-001');
    expect(audiobookPrepDashboardPayload.output_name).toBe('audiobook_prep_dashboard');
    expect(audiobookPrepDashboardPayload.project_id).toBe(projectId);
    expect(audiobookPrepDashboardPayload.run_id).toBe(runId);
    expect(audiobookPrepDashboardPayload.run_status).toBe('completed');
    expect(typeof audiobookPrepDashboardPayload.generated_at).toBe('string');
    expect(audiobookPrepDashboardPayload.unresolved_speaker_count).toBeGreaterThanOrEqual(0);
    expect(audiobookPrepDashboardPayload.unresolved_voice_mapping_count).toBeGreaterThanOrEqual(0);
    expect(audiobookPrepDashboardPayload.low_confidence_region_count).toBeGreaterThanOrEqual(0);
    expect(typeof audiobookPrepDashboardPayload.export_readiness.is_ready).toBe('boolean');
    expect(Array.isArray(audiobookPrepDashboardPayload.export_readiness.blocking_reasons)).toBe(true);
    expect(Array.isArray(audiobookPrepDashboardPayload.export_readiness.warning_reasons)).toBe(true);

    const cooccurrenceGraphResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/character-cooccurrence-graph`,
    );
    expect(cooccurrenceGraphResponse.status()).toBe(200);
    const cooccurrenceGraphPayload = (await cooccurrenceGraphResponse.json()) as {
      project_id: number;
      run_id: number;
      graph: {
        nodes: unknown[];
        edges: unknown[];
        metadata: {
          node_count: number;
          edge_count: number;
        };
      };
      character_cooccurrence_centrality: {
        metrics_table: unknown[];
      };
    };
    expect(cooccurrenceGraphPayload.project_id).toBe(projectId);
    expect(cooccurrenceGraphPayload.run_id).toBe(runId);
    expect(Array.isArray(cooccurrenceGraphPayload.graph.nodes)).toBe(true);
    expect(Array.isArray(cooccurrenceGraphPayload.graph.edges)).toBe(true);
    expect(cooccurrenceGraphPayload.graph.nodes.length).toBe(cooccurrenceGraphPayload.graph.metadata.node_count);
    expect(cooccurrenceGraphPayload.character_cooccurrence_centrality.metrics_table).toBeInstanceOf(Array);

    const tensionGraphResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/tension-graph`);
    expect(tensionGraphResponse.status()).toBe(200);
    const tensionGraphPayload = (await tensionGraphResponse.json()) as {
      metric_id: string;
      value_key: string;
      points: Array<{ position: number; smoothed_tension: number }>;
      peak_markers: Array<{ prominence: number; tension_value: number }>;
      metadata: { smoothed_window_size?: number; peak_prominence_thresholds?: { major?: number; minor?: number } | null };
    };
    expect(tensionGraphPayload.metric_id).toBe('smoothed_tension_curve');
    expect(tensionGraphPayload.value_key).toBe('smoothed_tension');
    expect(tensionGraphPayload.points.length).toBeGreaterThan(0);
    expect(tensionGraphPayload.points.every((point) => typeof point.position === 'number')).toBe(true);
    expect(tensionGraphPayload.points.every((point) => typeof point.smoothed_tension === 'number')).toBe(true);
    expect(typeof tensionGraphPayload.metadata.smoothed_window_size).toBe('number');
    if (tensionGraphPayload.peak_markers.length > 0) {
      expect(tensionGraphPayload.peak_markers.every((marker) => typeof marker.prominence === 'number')).toBe(true);
      expect(tensionGraphPayload.peak_markers.every((marker) => typeof marker.tension_value === 'number')).toBe(true);
    }
    const peakProminenceThresholds = tensionGraphPayload.metadata.peak_prominence_thresholds;
    if (peakProminenceThresholds) {
      expect(typeof peakProminenceThresholds.major).toBe('number');
      expect(typeof peakProminenceThresholds.minor).toBe('number');
    }

    const polarityGraphResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/polarity-graph`);
    expect(polarityGraphResponse.status()).toBe(200);
    const polarityGraphPayload = (await polarityGraphResponse.json()) as {
      metric_id: string;
      value_key: string;
      points: Array<{ position: number; rolling_mean_valence: number; rolling_mean_intensity: number }>;
      metadata: { rolling_window_size?: number };
    };
    expect(polarityGraphPayload.metric_id).toBe('rolling_emotional_polarity');
    expect(polarityGraphPayload.value_key).toBe('rolling_mean_valence');
    expect(polarityGraphPayload.points.length).toBeGreaterThan(0);
    expect(polarityGraphPayload.points.every((point) => typeof point.position === 'number')).toBe(true);
    expect(polarityGraphPayload.points.every((point) => typeof point.rolling_mean_valence === 'number')).toBe(true);
    expect(polarityGraphPayload.points.every((point) => typeof point.rolling_mean_intensity === 'number')).toBe(true);
    expect(typeof polarityGraphPayload.metadata.rolling_window_size).toBe('number');

    const characterAnalyticsResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/character-analytics`,
    );
    expect(characterAnalyticsResponse.status()).toBe(200);
    const characterAnalyticsPayload = (await characterAnalyticsResponse.json()) as {
      project_id: number;
      run_id: number;
      character_mentions_by_chapter: Array<{ chapter_index: number; mention_counts: Record<string, number> }>;
      character_mentions_per_1000_words: Record<string, number>;
      character_dialogue_line_counts: Record<string, number>;
    };
    expect(characterAnalyticsPayload.project_id).toBe(projectId);
    expect(characterAnalyticsPayload.run_id).toBe(runId);
    expect(characterAnalyticsPayload.character_mentions_by_chapter.length).toBeGreaterThan(0);
    expect(Object.keys(characterAnalyticsPayload.character_mentions_per_1000_words).length).toBeGreaterThan(0);
    expect(Object.keys(characterAnalyticsPayload.character_dialogue_line_counts).length).toBeGreaterThan(0);
    expect(
      Object.values(characterAnalyticsPayload.character_mentions_per_1000_words).every(
        (prominenceValue) => typeof prominenceValue === 'number' && prominenceValue >= 0,
      ),
    ).toBe(true);

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

    const exportCsvResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runId}.csv`);
    expect(exportCsvResponse.status()).toBe(200);
    expect(exportCsvResponse.headers()['content-type']).toContain('text/csv');
    const exportCsvBody = await exportCsvResponse.text();
    const [csvHeader, firstCsvRow] = exportCsvBody.trim().split('\n');
    expect(csvHeader).toContain('segment_id');
    expect(csvHeader).toContain('normalized_text');
    expect(csvHeader).toContain('phonetic_text');
    expect(csvHeader).toContain('resolved_voice_id');
    expect(firstCsvRow).toBeTruthy();

    const incrementalAppendResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/append-chapter`, {
      multipart: {
        file: {
          name: 'append-chapter-4.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(
            'Chapter 4\nThe watchfire dimmed while the harbor bells echoed beneath the rain.',
          ),
        },
      },
    });
    expect(incrementalAppendResponse.status()).toBe(200);

    const incrementalRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: false,
        incremental_recompute: true,
      },
    });
    expect(incrementalRunResponse.status()).toBe(200);
    const incrementalRunPayload = (await incrementalRunResponse.json()) as { run_id: number };

    const incrementalExportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/exports/${incrementalRunPayload.run_id}.json`,
    );
    expect(incrementalExportResponse.status()).toBe(200);
    const incrementalExportPayload = (await incrementalExportResponse.json()) as {
      segments: Array<Record<string, unknown>>;
    };

    const baselineSegments = exportPayload.segments as Array<Record<string, unknown>>;
    const maxBaselineChapterId = Math.max(
      ...baselineSegments.map((segment) => Number(segment.chapter_id ?? 0)),
    );
    const incrementalPrefixSegments = incrementalExportPayload.segments.filter(
      (segment) => Number(segment.chapter_id ?? 0) <= maxBaselineChapterId,
    );
    expect(incrementalPrefixSegments).toEqual(baselineSegments);
    const incrementalAppendedSegments = incrementalExportPayload.segments.filter(
      (segment) => Number(segment.chapter_id ?? 0) > maxBaselineChapterId,
    );
    expect(incrementalAppendedSegments.length).toBeGreaterThan(0);

    const incrementalRunDetailResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${incrementalRunPayload.run_id}`,
    );
    expect(incrementalRunDetailResponse.status()).toBe(200);
    const incrementalRunDetailPayload = (await incrementalRunDetailResponse.json()) as {
      config: {
        incremental_recompute?: unknown;
      };
    };
    const incrementalRecomputeConfig = incrementalRunDetailPayload.config.incremental_recompute;
    if (typeof incrementalRecomputeConfig === 'boolean') {
      expect(incrementalRecomputeConfig).toBe(true);
    } else if (
      incrementalRecomputeConfig &&
      typeof incrementalRecomputeConfig === 'object' &&
      Object.hasOwn(incrementalRecomputeConfig as Record<string, unknown>, 'enabled')
    ) {
      expect((incrementalRecomputeConfig as { enabled?: boolean }).enabled).toBe(true);
    }

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
            {
              term: 'Nimble',
              verbalized_form: 'Nim-buhl',
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
      warnings?: Array<{ type: string; term?: string; scopes?: string[] }>;
      included_scopes: string[];
    };
    expect(previewPayload.project_id).toBe(projectId);
    expect(previewPayload.replacements.length).toBeGreaterThan(0);
    expect(previewPayload.before).toBe('Nimble and Atlantis meet Alice in Aegis and Avernus.');
    expect(previewPayload.after).toBe('Nim-buhl and At-Lan-tis meet Al-iss in EE-gis and Ah-vernus.');
    expect(previewPayload.after).toContain('Nim-buhl');
    expect(previewPayload.after).not.toContain('Nim-ble');
    expect(previewPayload.replacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          term: 'Nimble',
          verbalized_form: 'Nim-buhl',
          scope: 'character',
        }),
      ]),
    );
    expect(previewPayload.warnings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: 'ambiguous_replacement',
          term: 'Nimble',
          scopes: expect.arrayContaining(['character', 'global']),
        }),
      ]),
    );
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
        internal_thought_voice_policy: 'thought_voice',
        internal_thought_voice: 'custom_thought_voice',
      },
    });
    expect(voicesResponse.status()).toBe(200);
    const voicesPayload = (await voicesResponse.json()) as { voice_config: Record<string, string | undefined> };
    expect(voicesPayload.voice_config).toHaveProperty('narrator_voice', 'narrator_default');
    expect(voicesPayload.voice_config).toHaveProperty('male_default_voice', 'male_default');
    expect(voicesPayload.voice_config).toHaveProperty('female_default_voice', 'female_default');
    expect(voicesPayload.voice_config).toHaveProperty('neutral_default_voice', 'neutral_default');
    expect(voicesPayload.voice_config).toHaveProperty('unknown_default_voice', 'unknown_default');
    expect(voicesPayload.voice_config).toHaveProperty('internal_thought_voice_policy', 'thought_voice');
    expect(voicesPayload.voice_config).toHaveProperty('thought_voice', 'custom_thought_voice');

    const voicesInheritedRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        allow_unfinalized_character_map: true,
        max_segment_chars: 140,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
      },
    });
    expect(voicesInheritedRunResponse.status()).toBe(200);

    const voicesInheritedRunPayload = (await voicesInheritedRunResponse.json()) as { run_id: number };
    const voicesInheritedRunDetailResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${voicesInheritedRunPayload.run_id}`,
    );
    expect(voicesInheritedRunDetailResponse.status()).toBe(200);
    const voicesInheritedRunDetail = (await voicesInheritedRunDetailResponse.json()) as {
      config: { internal_thought_voice_policy: string; internal_thought_voice?: string };
    };
    expect(voicesInheritedRunDetail.config.internal_thought_voice_policy).toBe('thought_voice');
    expect(voicesInheritedRunDetail.config.internal_thought_voice).toBe('custom_thought_voice');

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
        gender: string;
        voice_id?: string;
        resolved_voice_id?: string;
        speaker_id: number | null;
        confidence: { speaker: number; emotion?: number };
        speaker_evidence?: { status?: string; method?: string };
        speaker_state?: string;
      }>;
    };

    expect(exportPayload.segments.every((segment) => typeof segment.speaker === 'string')).toBe(true);
    expect(exportPayload.segments.every((segment) => typeof segment.gender === 'string')).toBe(true);
    expect(exportPayload.segments.every((segment) => typeof segment.voice_id === 'string')).toBe(true);
    expect(exportPayload.segments.every((segment) => typeof segment.resolved_voice_id === 'string')).toBe(true);

    const attributableSegments = exportPayload.segments.filter((segment) => segment.speaker_id !== null);
    expect(attributableSegments.length).toBeGreaterThan(0);
    expect(attributableSegments.every((segment) => segment.speaker.toLowerCase() !== 'unknown')).toBe(true);
    expect(attributableSegments.every((segment) => segment.gender.toLowerCase() !== 'unknown')).toBe(true);
    expect(attributableSegments.every((segment) => segment.voice_id && segment.voice_id.length > 0)).toBe(true);
    expect(attributableSegments.every((segment) => segment.resolved_voice_id === segment.voice_id)).toBe(true);

    const resolvedSegment = exportPayload.segments.find((segment) => segment.speaker.toLowerCase() === 'alice');
    expect(resolvedSegment).toBeDefined();
    expect(typeof resolvedSegment?.speaker_id).toBe('number');
    expect(resolvedSegment?.speaker_id).toBeGreaterThan(0);
    expect(resolvedSegment?.gender).toBe('female');
    expect(typeof resolvedSegment?.voice_id).toBe('string');
    expect(typeof resolvedSegment?.resolved_voice_id).toBe('string');
    expect(resolvedSegment?.resolved_voice_id).toBe(resolvedSegment?.voice_id);
    expect(typeof resolvedSegment?.confidence.speaker).toBe('number');
    expect(resolvedSegment?.confidence.speaker).toBeGreaterThan(0.0);
    expect(typeof resolvedSegment?.speaker_evidence).toBe('object');
    expect(resolvedSegment?.speaker_evidence?.status).toBe('found');
    expect(typeof resolvedSegment?.speaker_state).toBe('string');
  });

  test('gender comparison detects and flags manual-inferred contradictions', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-gender-contradiction-flags'));
    const projectId = project.id;

    const upsertResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Nia',
            verbalized_form: 'Nia',
            gender: 'male',
            confidence: 1.0,
            inferred_gender: 'female',
            inferred_confidence: 0.91,
            inferred_source_trace: [],
          },
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'female',
            confidence: 1.0,
            inferred_gender: 'female',
            inferred_confidence: 0.89,
            inferred_source_trace: [],
          },
        ],
      },
    });
    expect(upsertResponse.status()).toBe(200);

    const comparisonResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/characters/gender-comparison`);
    expect(comparisonResponse.status()).toBe(200);
    const comparisonPayload = (await comparisonResponse.json()) as {
      comparison_count: number;
      contradiction_count: number;
      comparisons: Array<{
        name: string;
        is_contradiction: boolean;
        requires_review: boolean;
        contradiction_severity: number;
      }>;
      warnings: Array<{ type: string; character_name: string; requires_review: boolean; contradiction_severity: number }>;
    };
    expect(comparisonPayload.comparison_count).toBe(2);
    expect(comparisonPayload.contradiction_count).toBe(1);
    expect(comparisonPayload.warnings.length).toBe(1);
    expect(comparisonPayload.warnings[0].type).toBe('manual_inferred_gender_contradiction');
    expect(comparisonPayload.warnings[0].character_name).toBe('Nia');
    expect(comparisonPayload.warnings[0].requires_review).toBe(true);
    expect(comparisonPayload.warnings[0].contradiction_severity).toBeGreaterThan(0);

    const byName = Object.fromEntries(comparisonPayload.comparisons.map((entry) => [entry.name, entry]));
    expect(byName.Nia.is_contradiction).toBe(true);
    expect(byName.Nia.requires_review).toBe(true);
    expect(byName.Nia.contradiction_severity).toBeGreaterThan(0);
    expect(byName.Kai.is_contradiction).toBe(false);
    expect(byName.Kai.requires_review).toBe(false);
  });

  test('identical input and run config yield reproducible export segments', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-reproducible-outputs'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'reproducible-source.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(
            'Chapter 1\nStormlight traced the ruined arch while the sentries waited.\n\n'
              + 'Chapter 2\nBy dawn, the harbor lanterns dimmed and the bells fell silent.',
          ),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runPayload = {
      mode: 'author',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      allow_unfinalized_character_map: true,
      deterministic_mode: true,
      deterministic_seed: 20260226,
      randomization_config: {
        strategy: 'stable',
        shuffle_enabled: false,
      },
    };

    const firstRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: runPayload,
    });
    expect(firstRunResponse.status()).toBe(200);
    const firstRunPayload = (await firstRunResponse.json()) as { run_id: number };

    const secondRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: runPayload,
    });
    expect(secondRunResponse.status()).toBe(200);
    const secondRunPayload = (await secondRunResponse.json()) as { run_id: number };
    expect(secondRunPayload.run_id).not.toBe(firstRunPayload.run_id);

    const firstExportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/exports/${firstRunPayload.run_id}.json`,
    );
    expect(firstExportResponse.status()).toBe(200);
    const firstExportPayload = (await firstExportResponse.json()) as {
      status: string;
      segments: Array<Record<string, unknown>>;
    };
    expect(firstExportPayload.status).toBe('completed');

    const secondExportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/exports/${secondRunPayload.run_id}.json`,
    );
    expect(secondExportResponse.status()).toBe(200);
    const secondExportPayload = (await secondExportResponse.json()) as {
      status: string;
      segments: Array<Record<string, unknown>>;
    };
    expect(secondExportPayload.status).toBe('completed');

    expect(firstExportPayload.segments).toEqual(secondExportPayload.segments);
  });

  test('incremental append recompute preserves unaffected output segments', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-incremental-append-affected-only'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'incremental-source.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(
            'Chapter 1\nMoonlit waves battered the harbor wall through the night.\n\n'
              + 'Chapter 2\nAt dawn, the sentries found fresh tracks by the eastern gate.',
          ),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const baselineRunPayload = {
      mode: 'author',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      allow_unfinalized_character_map: true,
      deterministic_mode: true,
      deterministic_seed: 20260226,
      randomization_config: {
        strategy: 'stable',
        shuffle_enabled: false,
      },
    };

    const baselineRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: baselineRunPayload,
    });
    expect(baselineRunResponse.status()).toBe(200);
    const baselineRun = (await baselineRunResponse.json()) as { run_id: number };

    const baselineExportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/exports/${baselineRun.run_id}.json`,
    );
    expect(baselineExportResponse.status()).toBe(200);
    const baselineExport = (await baselineExportResponse.json()) as {
      status: string;
      segments: Array<Record<string, unknown>>;
    };
    expect(baselineExport.status).toBe('completed');
    expect(baselineExport.segments.length).toBeGreaterThan(0);

    const appendResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/append-chapter`, {
      multipart: {
        file: {
          name: 'append-chapter-3.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(
            'Chapter 3\nThe bells rang once, then silence spread over the flooded square.',
          ),
        },
      },
    });
    expect(appendResponse.status()).toBe(200);

    const incrementalRunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        ...baselineRunPayload,
        incremental_recompute: true,
      },
    });
    expect(incrementalRunResponse.status()).toBe(200);
    const incrementalRun = (await incrementalRunResponse.json()) as { run_id: number };

    const incrementalExportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/exports/${incrementalRun.run_id}.json`,
    );
    expect(incrementalExportResponse.status()).toBe(200);
    const incrementalExport = (await incrementalExportResponse.json()) as {
      status: string;
      segments: Array<Record<string, unknown>>;
    };
    expect(incrementalExport.status).toBe('completed');

    const maxBaselineChapterId = Math.max(
      ...(baselineExport.segments.map((segment) => Number(segment.chapter_id ?? 0))),
    );
    const incrementalPrefixSegments = incrementalExport.segments.filter(
      (segment) => Number(segment.chapter_id ?? 0) <= maxBaselineChapterId,
    );
    const incrementalAppendedSegments = incrementalExport.segments.filter(
      (segment) => Number(segment.chapter_id ?? 0) > maxBaselineChapterId,
    );

    expect(incrementalPrefixSegments).toEqual(baselineExport.segments);
    expect(incrementalAppendedSegments.length).toBeGreaterThan(0);
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
        emotion_evidence?: { method?: string };
        emotion_state?: string;
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    expect(
      exportPayload.segments.every(
        (entry) =>
          typeof entry.emotion_valence === 'number' &&
          entry.emotion_valence >= -1 &&
          entry.emotion_valence <= 1 &&
          typeof entry.emotion_intensity === 'number' &&
          entry.emotion_intensity >= 0 &&
          entry.emotion_intensity <= 1 &&
          typeof entry.emotion_primary_label === 'string' &&
          entry.emotion_primary_label.length > 0 &&
          typeof entry.emotion_secondary_label === 'string' &&
          entry.emotion_secondary_label.length > 0 &&
          typeof entry.confidence?.emotion === 'number' &&
          (entry.confidence?.emotion ?? 0) >= 0 &&
          (entry.confidence?.emotion ?? 0) <= 1,
      ),
    ).toBe(true);
    const segment = exportPayload.segments[0];
    expect(typeof segment.emotion_valence).toBe('number');
    expect(typeof segment.emotion_intensity).toBe('number');
    expect(Math.abs(segment.emotion_intensity)).toBeGreaterThanOrEqual(0);
    expect(segment.emotion_primary_label).toMatch(/(positive|negative|neutral)/);
    expect(segment.emotion_secondary_label).toBeTruthy();
    expect(typeof segment.confidence.emotion).toBe('number');
    expect(typeof segment.emotion_evidence).toBe('object');
    expect(typeof segment.emotion_evidence?.method).toBe('string');
    expect(typeof segment.emotion_state).toBe('string');
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
      segments: Array<{
        tension_contribution?: {
          value: number;
          level: string;
          confidence?: number;
          state?: string;
          evidence?: Record<string, unknown>;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.tension_contribution).toBeDefined();
    expect(typeof firstSegment.tension_contribution).toBe('object');
    expect(typeof firstSegment.tension_contribution?.value).toBe('number');
    expect(typeof firstSegment.tension_contribution?.level).toBe('string');
    expect(typeof firstSegment.tension_contribution?.confidence).toBe('number');
    expect(typeof firstSegment.tension_contribution?.state).toBe('string');
    expect(typeof firstSegment.tension_contribution?.evidence).toBe('object');
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
      segments: Array<{
        dominance_contribution?: {
          value: number;
          level: string;
          dominant_agent: string;
          state?: string;
          evidence: Record<string, unknown>;
        };
      }>;
    };

    expect(exportPayload.segments.length).toBeGreaterThan(0);
    const firstSegment = exportPayload.segments[0];
    expect(firstSegment.dominance_contribution).toBeDefined();
    expect(typeof firstSegment.dominance_contribution).toBe('object');
    expect(typeof firstSegment.dominance_contribution?.value).toBe('number');
    expect(typeof firstSegment.dominance_contribution?.level).toBe('string');
    expect(typeof firstSegment.dominance_contribution?.dominant_agent).toBe('string');
    expect(typeof firstSegment.dominance_contribution?.confidence).toBe('number');
    expect(typeof firstSegment.dominance_contribution?.state).toBe('string');
    expect(firstSegment.dominance_contribution?.dominant_agent.length).toBeGreaterThan(0);
    expect(typeof firstSegment.dominance_contribution?.evidence).toBe('object');
    expect(firstSegment.dominance_contribution?.value).toBeGreaterThanOrEqual(0);
    expect(firstSegment.dominance_contribution?.value).toBeLessThanOrEqual(1);
    expect(['dominant', 'strong', 'moderate', 'low']).toContain(firstSegment.dominance_contribution?.level);
  });

  test('pipeline can execute and export without relying on manual review steps', async ({ request }) => {
    const project = await createProject(request, uniqueTitle('e2e-no-review-required'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'no-review-required.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nThe corridor lights flickered while someone whispered warnings into the dark.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 140,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };
    expect(runPayload.run_id).toBeGreaterThan(0);

    const runDetailResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${runPayload.run_id}`);
    expect(runDetailResponse.status()).toBe(200);
    const runDetail = (await runDetailResponse.json()) as { status: string; segment_count: number };
    expect(runDetail.status).toBe('completed');
    expect(runDetail.segment_count).toBeGreaterThan(0);

    const exportResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`,
    );
    expect(exportResponse.status()).toBe(200);
    const exportPayload = (await exportResponse.json()) as { segments: object[] };
    expect(exportPayload.segments.length).toBeGreaterThan(0);
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
        tag_states?: {
          type?: string;
          speaker?: string;
          emotion?: string;
          tension?: string;
          dominance?: string;
          summary?: string;
        };
        type_confidence?: number;
        type_evidence?: { signals?: unknown[] };
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
    expect(typeof firstSegment.type_evidence).toBe('object');
    expect(Array.isArray(firstSegment.type_evidence?.signals)).toBe(true);
    expect(typeof firstSegment.tag_states).toBe('object');
    expect(typeof firstSegment.tag_states?.type).toBe('string');
    expect(typeof firstSegment.confidence?.type).toBe('number');
    expect(typeof firstSegment.confidence?.tension).toBe('number');
    expect(typeof firstSegment.confidence?.dominance).toBe('number');
  });
});
