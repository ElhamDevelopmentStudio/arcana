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

type ProjectAllowedActionsResponse = {
  project_id: number;
  lifecycle_state: string;
  last_run_status: string | null;
  next_required_action: string;
  allowed_actions: string[];
};
type ProjectDetailResponse = {
  project_id: number;
  title: string;
  lifecycle_state: string;
  next_required_action: string;
  allowed_actions: string[];
  selected_mode: string;
  selected_modes: string[];
  created_at: string;
  updated_at: string;
};
type ProjectLifecycleStateChangeResponse = {
  project_id: number;
  action: 'archive' | 'restore';
  previous_lifecycle_state: string;
  lifecycle_state: string;
  next_required_action: string;
  allowed_actions: string[];
};
type ProjectActivityTimelineResponse = {
  project_id: number;
  total_items: number;
  page: number;
  page_size: number;
  has_next_page: boolean;
  items: Array<{
    event_id: number;
    event_type: string;
    actor: string;
    run_id: number | null;
    created_at: string;
    event_metadata: Record<string, unknown>;
  }>;
};
type ProjectSetupStatusResponse = {
  is_complete: boolean;
  lifecycle_state: string;
  next_required_action: string;
  steps: Array<{
    step_id: string;
    required: boolean;
    ready: boolean;
  }>;
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

async function waitForSetupCompletion(
  request: Parameters<typeof test>[0]['request'],
  projectId: number,
  timeoutMs: number = 30_000,
) {
  const startedAt = Date.now();

  while (Date.now() - startedAt <= timeoutMs) {
    const setupStatusResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/setup-status`);
    expect(setupStatusResponse.status()).toBe(200);
    const setupStatusPayload = (await setupStatusResponse.json()) as ProjectSetupStatusResponse;
    if (setupStatusPayload.is_complete) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }

  throw new Error(`Timed out waiting for setup completion for project ${projectId}.`);
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

    const draftActionsResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/actions`);
    expect(draftActionsResponse.status()).toBe(200);
    const draftActionsPayload = (await draftActionsResponse.json()) as ProjectAllowedActionsResponse;
    expect(draftActionsPayload.project_id).toBe(projectId);
    expect(draftActionsPayload.allowed_actions).toEqual(
      expect.arrayContaining(['ingest', 'select_mode', 'configure', 'archive']),
    );
    expect(draftActionsPayload.allowed_actions).not.toContain('restore');

    const projectDetailResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}`);
    expect(projectDetailResponse.status()).toBe(200);
    const projectDetailPayload = (await projectDetailResponse.json()) as ProjectDetailResponse;
    expect(projectDetailPayload.project_id).toBe(projectId);
    expect(projectDetailPayload.lifecycle_state).toBe('draft');
    expect(projectDetailPayload.next_required_action).toBe('ingest');
    expect(projectDetailPayload.allowed_actions).toEqual(
      expect.arrayContaining(['ingest', 'select_mode', 'configure', 'archive']),
    );
    expect(projectDetailPayload.selected_mode).toBe('audiobook');
    expect(projectDetailPayload.created_at).toEqual(expect.any(String));
    expect(projectDetailPayload.updated_at).toEqual(expect.any(String));

    const archiveProjectResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/archive`);
    expect(archiveProjectResponse.status()).toBe(200);
    const archiveProjectPayload = (await archiveProjectResponse.json()) as ProjectLifecycleStateChangeResponse;
    expect(archiveProjectPayload.project_id).toBe(projectId);
    expect(archiveProjectPayload.action).toBe('archive');
    expect(archiveProjectPayload.previous_lifecycle_state).toBe('draft');
    expect(archiveProjectPayload.lifecycle_state).toBe('archived');
    expect(archiveProjectPayload.next_required_action).toBe('archived');
    expect(archiveProjectPayload.allowed_actions).toEqual(['restore']);

    const archivedActionsResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/actions`);
    expect(archivedActionsResponse.status()).toBe(200);
    const archivedActionsPayload = (await archivedActionsResponse.json()) as ProjectAllowedActionsResponse;
    expect(archivedActionsPayload.allowed_actions).toEqual(['restore']);

    const restoreProjectResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/restore`);
    expect(restoreProjectResponse.status()).toBe(200);
    const restoreProjectPayload = (await restoreProjectResponse.json()) as ProjectLifecycleStateChangeResponse;
    expect(restoreProjectPayload.project_id).toBe(projectId);
    expect(restoreProjectPayload.action).toBe('restore');
    expect(restoreProjectPayload.previous_lifecycle_state).toBe('archived');
    expect(restoreProjectPayload.lifecycle_state).toBe('draft');
    expect(restoreProjectPayload.next_required_action).toBe('ingest');
    expect(restoreProjectPayload.allowed_actions).toEqual(
      expect.arrayContaining(['ingest', 'select_mode', 'configure', 'archive']),
    );
    expect(restoreProjectPayload.allowed_actions).not.toContain('restore');

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
    const completedActionsResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/actions`);
    expect(completedActionsResponse.status()).toBe(200);
    const completedActionsPayload = (await completedActionsResponse.json()) as ProjectAllowedActionsResponse;
    expect(completedActionsPayload.project_id).toBe(projectId);
    expect(completedActionsPayload.last_run_status).toBe('completed');
    expect(completedActionsPayload.allowed_actions).toEqual(
      expect.arrayContaining(['run', 'export', 'archive']),
    );

    const rerunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/rerun`);
    expect(rerunResponse.status()).toBe(200);
    const rerunPayload = (await rerunResponse.json()) as { run_id: number; project_id: number; status: string };
    expect(rerunPayload.project_id).toBe(projectId);
    expect(rerunPayload.run_id).not.toBe(runId);
    expect(rerunPayload.status).toBe('completed');
    const rerunDetailResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${rerunPayload.run_id}`);
    expect(rerunDetailResponse.status()).toBe(200);
    const rerunDetailPayload = (await rerunDetailResponse.json()) as { config: Record<string, unknown> };
    expect(rerunDetailPayload.config.rerun_source_run_id).toBe(runId);
    expect(rerunDetailPayload.config.rerun_source_configuration_snapshot_id).toBeTruthy();
    expect(rerunDetailPayload.config.rerun_source_configuration_snapshot_version).toBeTruthy();
    expect(rerunDetailPayload.config.rerun_lineage_type).toBe('snapshot_clone');
    const timelineResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/timeline`, {
      params: { page: 1, page_size: 25 },
    });
    expect(timelineResponse.status()).toBe(200);
    const timelinePayload = (await timelineResponse.json()) as ProjectActivityTimelineResponse;
    expect(timelinePayload.project_id).toBe(projectId);
    expect(timelinePayload.total_items).toBeGreaterThan(0);
    expect(timelinePayload.page).toBe(1);
    expect(timelinePayload.page_size).toBe(25);
    expect(Array.isArray(timelinePayload.items)).toBe(true);
    const timelineEventTypes = timelinePayload.items.map((event) => event.event_type);
    expect(timelineEventTypes).toEqual(expect.arrayContaining(['run_start', 'run_complete', 'rerun']));
    expect(timelinePayload.items[0].event_id).toBeGreaterThan(0);
    expect(typeof timelinePayload.items[0].actor).toBe('string');

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

    const cancelCompletedRunResponse = await request.post(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/cancel`,
    );
    expect(cancelCompletedRunResponse.status()).toBe(409);
    const cancelCompletedRunPayload = (await cancelCompletedRunResponse.json()) as { detail: string };
    expect(cancelCompletedRunPayload.detail).toContain('Only queued or running runs can be cancelled');

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

    const pipelineStageDurationsDashboardResponse = await request.get(
      `${backendBaseUrl}/api/projects/${projectId}/runs/${runId}/pipeline-stage-durations-dashboard`,
    );
    expect(pipelineStageDurationsDashboardResponse.status()).toBe(200);
    const pipelineStageDurationsDashboardPayload = (await pipelineStageDurationsDashboardResponse.json()) as {
      schema_version: string;
      output_schema: string;
      output_format: string;
      output_id: string;
      output_name: string;
      project_id: number;
      run_id: number;
      run_status: string;
      generated_at: string;
      total_duration_ms: number;
      stage_count: number;
      slowest_stage_name: string | null;
      slowest_stage_duration_ms: number | null;
      stages: Array<{
        stage_name: string;
        duration_ms: number;
        share_of_total: number;
      }>;
    };
    expect(pipelineStageDurationsDashboardPayload.schema_version).toBe('1.0.0');
    expect(pipelineStageDurationsDashboardPayload.output_schema).toBe('pipeline_stage_durations_dashboard_json');
    expect(pipelineStageDurationsDashboardPayload.output_format).toBe('json');
    expect(pipelineStageDurationsDashboardPayload.output_id).toBe('OBS-001');
    expect(pipelineStageDurationsDashboardPayload.output_name).toBe('pipeline_stage_durations_dashboard');
    expect(pipelineStageDurationsDashboardPayload.project_id).toBe(projectId);
    expect(pipelineStageDurationsDashboardPayload.run_id).toBe(runId);
    expect(pipelineStageDurationsDashboardPayload.run_status).toBe('completed');
    expect(typeof pipelineStageDurationsDashboardPayload.generated_at).toBe('string');
    expect(pipelineStageDurationsDashboardPayload.total_duration_ms).toBeGreaterThanOrEqual(0);
    expect(pipelineStageDurationsDashboardPayload.stage_count).toBeGreaterThan(0);
    expect(Array.isArray(pipelineStageDurationsDashboardPayload.stages)).toBe(true);
    expect(pipelineStageDurationsDashboardPayload.stages.length).toBe(
      pipelineStageDurationsDashboardPayload.stage_count,
    );
    expect(
      pipelineStageDurationsDashboardPayload.stages.some((stage) => stage.stage_name === 'load_and_validate_source_data'),
    ).toBe(true);
    expect(
      pipelineStageDurationsDashboardPayload.stages.every(
        (stage) =>
          typeof stage.duration_ms === 'number'
          && stage.duration_ms >= 0
          && typeof stage.share_of_total === 'number'
          && stage.share_of_total >= 0
          && stage.share_of_total <= 1,
      ),
    ).toBe(true);
    expect(typeof pipelineStageDurationsDashboardPayload.slowest_stage_name === 'string').toBe(true);
    expect(
      pipelineStageDurationsDashboardPayload.slowest_stage_duration_ms === null
      || pipelineStageDurationsDashboardPayload.slowest_stage_duration_ms >= 0,
    ).toBe(true);

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
    await page.getByTestId('mode-switch-confirm-submit').click();
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

  test('projects/:project_id/mode route requests mode catalog and updates mode through switch endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-mode-route-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeCatalogRequestPromise = page.waitForRequest(
      (networkRequest) => networkRequest.method() === 'GET' && networkRequest.url().endsWith('/api/modes'),
    );
    const modeCatalogResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' && networkResponse.url().endsWith('/api/modes'),
    );

    await page.goto(`/projects/${projectId}/mode`);
    await expect(page.getByTestId('mode-select')).toBeVisible();

    await modeCatalogRequestPromise;
    const modeCatalogResponse = await modeCatalogResponsePromise;
    expect(modeCatalogResponse.status()).toBe(200);

    const modeSwitchRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PUT' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/mode`),
    );
    const modeSwitchResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PUT' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/mode`),
    );

    await page.getByTestId('mode-select').selectOption('author');
    await page.getByTestId('mode-switch-confirm-submit').click();
    const modeSwitchRequest = await modeSwitchRequestPromise;
    const modeSwitchPayload = modeSwitchRequest.postDataJSON() as { mode: string };
    expect(modeSwitchPayload.mode).toBe('author');

    const modeSwitchResponse = await modeSwitchResponsePromise;
    expect(modeSwitchResponse.status()).toBe(200);
    await expect(page.getByTestId('mode-continue-button')).toBeEnabled();
  });

  test('projects/:project_id/characters route reads and saves character map through backend endpoints', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-route-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
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
    expect(seedCharacterMapResponse.status()).toBe(200);

    const charactersGetRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters`),
    );
    const charactersGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters`),
    );

    await page.goto(`/projects/${projectId}/characters`);
    await expect(page.getByTestId('character-map-save-button')).toBeVisible();

    await charactersGetRequestPromise;
    const charactersGetResponse = await charactersGetResponsePromise;
    expect(charactersGetResponse.status()).toBe(200);
    await expect(page.getByTestId('character-list-state')).toContainText('1 row(s) loaded.');

    const charactersPutRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PUT' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters`),
    );
    const charactersPutResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PUT' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters`),
    );

    await page.getByTestId('character-map-save-button').click();

    const charactersPutRequest = await charactersPutRequestPromise;
    const charactersPutPayload = charactersPutRequest.postDataJSON() as {
      characters: Array<{ name: string; verbalized_form: string; gender: string }>;
    };
    expect(charactersPutPayload.characters.length).toBeGreaterThan(0);
    expect(charactersPutPayload.characters[0]?.name).toBe('Alice');
    expect(charactersPutPayload.characters[0]?.verbalized_form).toBe('Alice');
    expect(charactersPutPayload.characters[0]?.gender).toBe('female');

    const charactersPutResponse = await charactersPutResponsePromise;
    expect(charactersPutResponse.status()).toBe(200);
  });

  test('projects/:project_id/characters route imports character map through backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-import-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    const charactersGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters`),
    );
    await page.goto(`/projects/${projectId}/characters`);
    await charactersGetResponsePromise;

    const importRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters/import`),
    );
    const importResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters/import`),
    );

    await page.getByTestId('character-file-input').setInputFiles(fixtureCharactersPath);
    await page.getByTestId('character-import-button').click();

    await importRequestPromise;
    const importResponse = await importResponsePromise;
    expect(importResponse.status()).toBe(200);
    const importPayload = (await importResponse.json()) as { imported_count: number };
    expect(importPayload.imported_count).toBeGreaterThan(0);
    await expect(page.getByTestId('character-import-state')).toContainText('Imported');
  });

  test('projects/:project_id/characters route runs character extraction through backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-extract-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    const charactersGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters`),
    );
    await page.goto(`/projects/${projectId}/characters`);
    await charactersGetResponsePromise;

    const extractRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters/extract`),
    );
    const extractResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters/extract`),
    );

    await page.getByRole('button', { name: 'Extract candidate names from text' }).click();

    await extractRequestPromise;
    const extractResponse = await extractResponsePromise;
    expect(extractResponse.status()).toBe(200);
    const extractPayload = (await extractResponse.json()) as { status: string; candidate_count: number };
    expect(extractPayload.status).toBe('complete');
    expect(extractPayload.candidate_count).toBeGreaterThanOrEqual(0);
    await expect(page.getByTestId('character-auto-extract-state')).toBeVisible();
  });

  test('projects/:project_id/characters route runs scrape-assisted candidate flow through backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-scrape-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    const charactersGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters`),
    );
    await page.goto(`/projects/${projectId}/characters`);
    await charactersGetResponsePromise;
    const scrapeSourceUrl = `${backendBaseUrl}/health`;

    const scrapeInput = page.getByLabel('Character scrape source URL');
    if ((await scrapeInput.count()) > 0) {
      const scrapeRequestPromise = page.waitForRequest(
        (networkRequest) =>
          networkRequest.method() === 'POST' &&
          networkRequest.url().endsWith(`/api/projects/${projectId}/characters/scrape`),
      );
      const scrapeResponsePromise = page.waitForResponse(
        (networkResponse) =>
          networkResponse.request().method() === 'POST' &&
          networkResponse.url().endsWith(`/api/projects/${projectId}/characters/scrape`),
      );

      await scrapeInput.fill(scrapeSourceUrl);
      await page.getByLabel('Acknowledge scrape warning').click();
      await page.getByRole('button', { name: 'Scrape candidates' }).click();

      const scrapeRequest = await scrapeRequestPromise;
      const scrapePayload = scrapeRequest.postDataJSON() as { source_url: string; acknowledge_source_risk: boolean };
      expect(scrapePayload.source_url).toBe(scrapeSourceUrl);
      expect(scrapePayload.acknowledge_source_risk).toBe(true);

      const scrapeResponse = await scrapeResponsePromise;
      expect(scrapeResponse.status()).toBe(200);
      const scrapeResponsePayload = (await scrapeResponse.json()) as { status: string; candidate_count: number };
      expect(scrapeResponsePayload.status).toBe('complete');
      expect(scrapeResponsePayload.candidate_count).toBeGreaterThanOrEqual(0);
      await expect(page.getByTestId('character-scrape-state')).toBeVisible();
      return;
    }

    await expect(page.getByText('Disabled by environment flag')).toBeVisible();
    const fallbackScrapeResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/scrape`, {
      data: {
        source_url: scrapeSourceUrl,
        acknowledge_source_risk: true,
      },
    });
    expect(fallbackScrapeResponse.status()).toBe(200);
    const fallbackScrapePayload = (await fallbackScrapeResponse.json()) as { status: string; candidate_count: number };
    expect(fallbackScrapePayload.status).toBe('complete');
    expect(fallbackScrapePayload.candidate_count).toBeGreaterThanOrEqual(0);
  });

  test('projects/:project_id/characters route runs merged-candidates flow through backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-merge-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    const charactersGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters`),
    );
    await page.goto(`/projects/${projectId}/characters`);
    await charactersGetResponsePromise;

    const mergedRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters/merged-candidates`),
    );
    const mergedResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters/merged-candidates`),
    );
    await page.getByRole('button', { name: 'Merge user + auto + scraped candidates' }).click();

    const mergedRequest = await mergedRequestPromise;
    const mergedPayload = mergedRequest.postDataJSON() as {
      include_auto: boolean;
      source_url?: string;
      acknowledge_source_risk?: boolean;
    };
    expect(mergedPayload.include_auto).toBe(true);
    expect(mergedPayload.source_url === undefined || mergedPayload.source_url === null || mergedPayload.source_url === '').toBe(true);

    const mergedResponse = await mergedResponsePromise;
    expect(mergedResponse.status()).toBe(200);
    const mergedResponsePayload = (await mergedResponse.json()) as { status: string; candidate_count: number };
    expect(mergedResponsePayload.status).toBe('complete');
    expect(mergedResponsePayload.candidate_count).toBeGreaterThanOrEqual(0);
    await expect(page.getByTestId('character-merged-state')).toBeVisible();
  });

  test('projects/:project_id/characters route runs gender inference action through backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-infer-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    const charactersGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters`),
    );
    await page.goto(`/projects/${projectId}/characters`);
    await charactersGetResponsePromise;

    const inferRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters/infer`),
    );
    const inferResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters/infer`),
    );
    await page.getByRole('button', { name: 'Infer Character Genders' }).click();

    await inferRequestPromise;
    const inferResponse = await inferResponsePromise;
    expect(inferResponse.status()).toBe(200);
    const inferPayload = (await inferResponse.json()) as {
      project_id: number;
      character_map_finalized: boolean;
      characters: Array<{ inferred_gender: string }>;
    };
    expect(inferPayload.project_id).toBe(projectId);
    expect(Array.isArray(inferPayload.characters)).toBe(true);
    expect(inferPayload.characters.length).toBeGreaterThanOrEqual(0);
  });

  test('projects/:project_id/characters route renders gender comparison review panel from backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-gender-panel-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);
    const inferResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/characters/infer`);
    expect(inferResponse.status()).toBe(200);

    const comparisonGetRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().includes(`/api/projects/${projectId}/characters/gender-comparison`),
    );
    const comparisonGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().includes(`/api/projects/${projectId}/characters/gender-comparison`),
    );

    await page.goto(`/projects/${projectId}/characters`);
    await comparisonGetRequestPromise;
    const comparisonGetResponse = await comparisonGetResponsePromise;
    expect(comparisonGetResponse.status()).toBe(200);
    await expect(page.getByTestId('character-gender-comparison-panel')).toBeVisible();
    await expect(page.getByTestId('character-gender-comparison-count')).toContainText('comparison row(s)');
  });

  test('projects/:project_id/characters route runs alias lookup utility through backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-alias-lookup-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/characters`);

    const aliasLookupRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters/lookup-alias`),
    );
    const aliasLookupResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters/lookup-alias`),
    );

    await page.getByTestId('character-alias-lookup-input').fill('K');
    await page.getByTestId('character-alias-lookup-button').click();

    const aliasLookupRequest = await aliasLookupRequestPromise;
    const aliasLookupPayload = aliasLookupRequest.postDataJSON() as { alias: string };
    expect(aliasLookupPayload.alias).toBe('K');

    const aliasLookupResponse = await aliasLookupResponsePromise;
    expect(aliasLookupResponse.status()).toBe(200);
    const aliasLookupResponsePayload = (await aliasLookupResponse.json()) as {
      alias: string;
      canonical_name: string | null;
      match_source: string;
    };
    expect(aliasLookupResponsePayload.alias).toBe('K');
    expect(aliasLookupResponsePayload.canonical_name).toBe('Kai');
    await expect(page.getByTestId('character-alias-lookup-state')).toContainText('K → Kai');
  });

  test('projects/:project_id/characters route renders alias collision inspector from backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-alias-collision-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
          {
            name: 'Kade',
            verbalized_form: 'Kade',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    const aliasCollisionsRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters/alias-collisions`),
    );
    const aliasCollisionsResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters/alias-collisions`),
    );

    await page.goto(`/projects/${projectId}/characters`);
    await aliasCollisionsRequestPromise;
    const aliasCollisionsResponse = await aliasCollisionsResponsePromise;
    expect(aliasCollisionsResponse.status()).toBe(200);
    await expect(page.getByTestId('character-alias-collision-inspector')).toBeVisible();
    await expect(page.getByTestId('character-alias-collision-inspector-count')).toContainText('collision group(s)');
  });

  test('projects/:project_id/characters route finalizes character map through backend endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-characters-finalize-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const seedCharacterMapResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/characters`, {
      data: {
        characters: [
          {
            name: 'Kai',
            verbalized_form: 'Kai',
            gender: 'male',
            aliases: ['K'],
            source: 'manual',
            confidence: 1.0,
          },
        ],
      },
    });
    expect(seedCharacterMapResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/characters`);

    const finalizeRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/characters/finalize`),
    );
    const finalizeResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/characters/finalize`),
    );

    await page.getByRole('button', { name: 'Finalize Character Map' }).click();

    await finalizeRequestPromise;
    const finalizeResponse = await finalizeResponsePromise;
    expect(finalizeResponse.status()).toBe(200);
    const finalizePayload = (await finalizeResponse.json()) as {
      project_id: number;
      character_map_finalized: boolean;
    };
    expect(finalizePayload.project_id).toBe(projectId);
    expect(finalizePayload.character_map_finalized).toBe(true);
    await expect(page.getByRole('button', { name: 'Character Map Finalized' })).toBeVisible();
  });

  test('projects/:project_id/characters route reads and updates artifact pronunciation scope through backend endpoints', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-pronunciation-artifacts-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const artifactsGetRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/artifacts`),
    );
    const artifactsGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/artifacts`),
    );

    await page.goto(`/projects/${projectId}/characters`);
    await artifactsGetRequestPromise;
    const artifactsGetResponse = await artifactsGetResponsePromise;
    expect(artifactsGetResponse.status()).toBe(200);
    await expect(page.getByTestId('pronunciation-artifacts-panel')).toBeVisible();

    const artifactsPutRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PUT' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/artifacts`),
    );
    const artifactsPutResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PUT' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/artifacts`),
    );

    await page.getByTestId('pronunciation-artifacts-textarea').fill('Aegis|EE-gis');
    await page.getByTestId('pronunciation-artifacts-save-button').click();

    const artifactsPutRequest = await artifactsPutRequestPromise;
    const artifactsPutPayload = artifactsPutRequest.postDataJSON() as {
      entries: Array<{ term: string; verbalized_form: string; source: string; confidence: number }>;
    };
    expect(artifactsPutPayload.entries).toEqual([
      {
        term: 'Aegis',
        verbalized_form: 'EE-gis',
        source: 'user',
        confidence: 1,
      },
    ]);

    const artifactsPutResponse = await artifactsPutResponsePromise;
    expect(artifactsPutResponse.status()).toBe(200);
    await expect(page.getByTestId('pronunciation-artifacts-state')).toContainText('Saved entries: 1');
  });

  test('projects/:project_id/characters route reads and updates invented pronunciation scope through backend endpoints', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-pronunciation-invented-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const inventedGetRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/invented`),
    );
    const inventedGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/invented`),
    );

    await page.goto(`/projects/${projectId}/characters`);
    await inventedGetRequestPromise;
    const inventedGetResponse = await inventedGetResponsePromise;
    expect(inventedGetResponse.status()).toBe(200);
    await expect(page.getByTestId('pronunciation-invented-panel')).toBeVisible();

    const inventedPutRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PUT' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/invented`),
    );
    const inventedPutResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PUT' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/pronunciation-dictionary/invented`),
    );

    await page.getByTestId('pronunciation-invented-textarea').fill('Aethercore|EE-ther-core');
    await page.getByTestId('pronunciation-invented-save-button').click();

    const inventedPutRequest = await inventedPutRequestPromise;
    const inventedPutPayload = inventedPutRequest.postDataJSON() as {
      entries: Array<{ term: string; verbalized_form: string; source: string; confidence: number }>;
    };
    expect(inventedPutPayload.entries).toEqual([
      {
        term: 'Aethercore',
        verbalized_form: 'EE-ther-core',
        source: 'user',
        confidence: 1,
      },
    ]);

    const inventedPutResponse = await inventedPutResponsePromise;
    expect(inventedPutResponse.status()).toBe(200);
    await expect(page.getByTestId('pronunciation-invented-state')).toContainText('Saved entries: 1');
  });

  test('projects/:project_id/settings route reads and updates project llm settings through backend endpoints', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-project-settings-route-contract');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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

    const accessGrantResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/access`, {
      data: {
        principal_id: 'qa-settings-user',
        principal_type: 'user',
        role: 'viewer',
      },
    });
    expect(accessGrantResponse.status()).toBe(201);
    const accessGrantPayload = (await accessGrantResponse.json()) as { id: number };

    await waitForSetupCompletion(request, projectId);

    const llmSettingsGetRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/llm`),
    );
    const llmSettingsGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/llm`),
    );
    const providersGetRequestPromise = page.waitForRequest(
      (networkRequest) => networkRequest.method() === 'GET' && networkRequest.url().endsWith('/api/llm/providers'),
    );
    const providersGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' && networkResponse.url().endsWith('/api/llm/providers'),
    );
    const accessListGetRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/access`),
    );
    const accessListGetResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'GET' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/access`),
    );

    await page.goto(`/projects/${projectId}/settings`);
    await expect(page.getByTestId('project-settings-llm-panel')).toBeVisible();
    await expect(page.getByTestId('project-settings-providers-panel')).toBeVisible();
    await expect(page.getByTestId('project-settings-access-panel')).toBeVisible();
    await expect(page.getByTestId('project-settings-access-no-auth-notice')).toContainText(
      'Authentication is not enabled in this environment.',
    );

    await llmSettingsGetRequestPromise;
    const llmSettingsGetResponse = await llmSettingsGetResponsePromise;
    expect(llmSettingsGetResponse.status()).toBe(200);
    await providersGetRequestPromise;
    const providersGetResponse = await providersGetResponsePromise;
    expect(providersGetResponse.status()).toBe(200);
    await accessListGetRequestPromise;
    const accessListGetResponse = await accessListGetResponsePromise;
    expect(accessListGetResponse.status()).toBe(200);
    await expect(page.getByTestId(`project-settings-access-grant-${accessGrantPayload.id}`)).toContainText(
      'qa-settings-user',
    );

    const accessGrantUiRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/access`),
    );
    const accessGrantUiResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/access`),
    );
    await page.getByTestId('project-settings-access-principal-id').fill('qa-settings-service');
    await page.getByTestId('project-settings-access-principal-type').selectOption('service');
    await page.getByTestId('project-settings-access-role').selectOption('editor');
    await page.getByTestId('project-settings-access-grant-submit').click();
    const accessGrantUiRequest = await accessGrantUiRequestPromise;
    const accessGrantUiPayload = accessGrantUiRequest.postDataJSON() as {
      principal_id: string;
      principal_type: string;
      role: string;
    };
    expect(accessGrantUiPayload).toEqual({
      principal_id: 'qa-settings-service',
      principal_type: 'service',
      role: 'editor',
    });
    const accessGrantUiResponse = await accessGrantUiResponsePromise;
    expect(accessGrantUiResponse.status()).toBe(201);

    const llmSettingsPutRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PUT' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/llm`),
    );
    const llmSettingsPutResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PUT' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/llm`),
    );

    await page.getByTestId('project-settings-llm-toggle').click();
    await page.getByTestId('project-settings-llm-save').click();

    const llmSettingsPutRequest = await llmSettingsPutRequestPromise;
    const llmSettingsPutPayload = llmSettingsPutRequest.postDataJSON() as { llm_enabled: boolean };
    expect(llmSettingsPutPayload.llm_enabled).toBe(true);

    const llmSettingsPutResponse = await llmSettingsPutResponsePromise;
    expect(llmSettingsPutResponse.status()).toBe(200);
    await expect(page.getByTestId('project-settings-llm-current')).toContainText('enabled');

    const firstProviderRow = page.locator('[data-testid^="project-settings-provider-row-"]').first();
    await expect(firstProviderRow).toBeVisible();
    const firstProviderRowTestId = await firstProviderRow.getAttribute('data-testid');
    expect(firstProviderRowTestId).toBeTruthy();
    const providerName = String(firstProviderRowTestId).replace('project-settings-provider-row-', '');
    const providerCurrentTestId = `project-settings-provider-current-${providerName}`;
    const providerToggleTestId = `project-settings-provider-toggle-${providerName}`;
    const providerSaveTestId = `project-settings-provider-save-${providerName}`;
    const providerCurrentText = await page.getByTestId(providerCurrentTestId).innerText();
    const providerInitiallyEnabled = providerCurrentText.includes('Current: enabled');
    const providerNextEnabled = !providerInitiallyEnabled;

    const providerPutRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PUT' &&
        networkRequest.url().endsWith(`/api/llm/providers/${providerName}`),
    );
    const providerPutResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PUT' &&
        networkResponse.url().endsWith(`/api/llm/providers/${providerName}`),
    );

    await page.getByTestId(providerToggleTestId).click();
    await page.getByTestId(providerSaveTestId).click();

    const providerPutRequest = await providerPutRequestPromise;
    const providerPutPayload = providerPutRequest.postDataJSON() as { enabled: boolean };
    expect(providerPutPayload.enabled).toBe(providerNextEnabled);

    const providerPutResponse = await providerPutResponsePromise;
    expect(providerPutResponse.status()).toBe(200);

    const providerRestoreRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PUT' &&
        networkRequest.url().endsWith(`/api/llm/providers/${providerName}`),
    );
    const providerRestoreResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PUT' &&
        networkResponse.url().endsWith(`/api/llm/providers/${providerName}`),
    );

    await page.getByTestId(providerToggleTestId).click();
    await page.getByTestId(providerSaveTestId).click();

    const providerRestoreRequest = await providerRestoreRequestPromise;
    const providerRestorePayload = providerRestoreRequest.postDataJSON() as { enabled: boolean };
    expect(providerRestorePayload.enabled).toBe(providerInitiallyEnabled);

    const providerRestoreResponse = await providerRestoreResponsePromise;
    expect(providerRestoreResponse.status()).toBe(200);
  });

  test('projects/new draft creation mode calls draft endpoint and persists workspace project id', async ({ page }) => {
    await page.goto('/projects/new');
    const title = uniqueTitle('e2e-ui-draft-mode');

    const draftCreateRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' && networkRequest.url().endsWith('/api/projects/drafts'),
    );
    const draftCreateResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' && networkResponse.url().endsWith('/api/projects/drafts'),
    );

    await page.getByTestId('project-creation-mode-select').selectOption('draft');
    await page.getByTestId('project-title-input').fill(title);
    await page.getByTestId('create-project-button').click();

    const draftCreateRequest = await draftCreateRequestPromise;
    const draftCreateRequestBody = draftCreateRequest.postDataJSON() as {
      title: string;
      do_not_store_source_text: boolean;
    };
    expect(draftCreateRequestBody.title).toBe(title);
    expect(draftCreateRequestBody.do_not_store_source_text).toBe(false);

    const draftCreateResponse = await draftCreateResponsePromise;
    expect(draftCreateResponse.status()).toBe(201);

    await expect(page.getByTestId('project-created-state')).toContainText('Current project ID:');
    const workspaceState = await readWorkspaceState(page);
    expect(workspaceState?.projectId).toBeGreaterThan(0);
  });

  test('projects/:project_id workspace home renders project detail contract data', async ({ page, request }) => {
    const title = uniqueTitle('e2e-workspace-home-detail');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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

    await waitForSetupCompletion(request, projectId);

    await page.goto(`/projects/${projectId}`);
    await expect(page).toHaveURL(`/projects/${projectId}`);
    await expect(page.getByTestId('project-workspace-home-ready')).toBeVisible();
    await expect(page.getByTestId('project-workspace-home-source-contract')).toContainText(
      'GET /api/projects/{project_id}',
    );
    await expect(page.getByTestId('project-workspace-home-title')).toContainText(title);
    await expect(page.getByTestId('project-workspace-home-id')).toContainText(`Project ID: ${projectId}`);
  });

  test('projects/:project_id next-required-action link resolves to the mapped workflow route', async ({ page, request }) => {
    const title = uniqueTitle('e2e-workspace-home-next-action');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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

    await waitForSetupCompletion(request, projectId);

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId('project-workspace-home-ready')).toBeVisible();

    const nextActionText = (await page.getByTestId('project-workspace-home-next-action').textContent()) ?? '';
    const nextAction = nextActionText.replace('Next action:', '').trim();
    const expectedRouteByAction: Record<string, string> = {
      ingest: `/projects/${projectId}/setup`,
      select_mode: `/projects/${projectId}/mode`,
      configure: `/projects/${projectId}/pipeline-setup`,
      run: `/projects/${projectId}/pipeline-setup`,
      rerun: `/projects/${projectId}/runs`,
      review_failure: `/projects/${projectId}/runs`,
      export: `/projects/${projectId}/exports`,
      archived: `/projects/${projectId}/settings`,
      none: `/projects/${projectId}/overview`,
    };
    const expectedRoute = expectedRouteByAction[nextAction] ?? `/projects/${projectId}/setup`;

    await expect(page.getByTestId('project-workspace-home-next-action-link')).toHaveAttribute('href', expectedRoute);
  });

  test('projects/:project_id metadata form updates project metadata through patch endpoint', async ({ page, request }) => {
    const title = uniqueTitle('e2e-workspace-home-metadata');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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

    await waitForSetupCompletion(request, projectId);

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId('project-workspace-home-ready')).toBeVisible();

    const nextTitle = `${title}-updated`;
    const nextDescription = 'Updated project metadata description from workspace home.';
    const nextTagsInput = 'Arc, Research, arc';

    const metadataPatchRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'PATCH' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/metadata`),
    );
    const metadataPatchResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'PATCH' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/metadata`),
    );

    await page.getByTestId('project-metadata-title-input').fill(nextTitle);
    await page.getByTestId('project-metadata-description-input').fill(nextDescription);
    await page.getByTestId('project-metadata-tags-input').fill(nextTagsInput);
    await page.getByTestId('project-metadata-save-button').click();

    const metadataPatchRequest = await metadataPatchRequestPromise;
    const metadataPatchBody = metadataPatchRequest.postDataJSON() as {
      title?: string;
      description?: string | null;
      tags?: string[];
    };
    expect(metadataPatchBody.title).toBe(nextTitle);
    expect(metadataPatchBody.description).toBe(nextDescription);
    expect(metadataPatchBody.tags).toEqual(['Arc', 'Research', 'arc']);

    const metadataPatchResponse = await metadataPatchResponsePromise;
    expect(metadataPatchResponse.status()).toBe(200);

    const projectDetailResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}`);
    expect(projectDetailResponse.status()).toBe(200);
    const projectDetailPayload = (await projectDetailResponse.json()) as ProjectDetailResponse;
    expect(projectDetailPayload.title).toBe(nextTitle);
    expect(projectDetailPayload.description).toBe(nextDescription);
    expect(projectDetailPayload.tags).toEqual(['Arc', 'Research']);
  });

  test('projects/:project_id command panel reflects allowed actions endpoint response', async ({ page, request }) => {
    const title = uniqueTitle('e2e-workspace-home-actions');
    const project = await createProject(request, title);
    const projectId = project.id;

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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

    await waitForSetupCompletion(request, projectId);

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId('project-command-panel')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-allowed-action-run')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-allowed-action-export')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-open-runs')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-open-exports')).toBeVisible();

    const archiveResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/archive`);
    expect(archiveResponse.status()).toBe(200);
    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId('project-command-panel-required-step')).toContainText('restore');
    await expect(page.getByTestId('project-command-panel-blocked-reason')).toContainText('Restore');
    await expect(page.getByTestId('project-command-panel-open-runs-disabled')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-open-exports-disabled')).toBeVisible();
  });

  test('projects/:project_id timeline panel renders paginated activity events', async ({ page, request }) => {
    const title = uniqueTitle('e2e-workspace-home-timeline');
    const project = await createProject(request, title);
    const projectId = project.id;

    for (let index = 0; index < 3; index += 1) {
      const metadataResponse = await request.patch(`${backendBaseUrl}/api/projects/${projectId}/metadata`, {
        data: {
          title: `${title}-v${index + 1}`,
          description: `Timeline enrichment ${index + 1}`,
          tags: ['timeline', `v${index + 1}`],
        },
      });
      expect(metadataResponse.status()).toBe(200);
    }

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

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

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);

    await waitForSetupCompletion(request, projectId);

    const timelinePageOneRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().includes(`/api/projects/${projectId}/timeline`) &&
        networkRequest.url().includes('page=1') &&
        networkRequest.url().includes('page_size=5'),
    );

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId('project-timeline-panel')).toBeVisible();
    await timelinePageOneRequestPromise;
    await expect(page.locator('[data-testid^="project-timeline-item-"]')).toHaveCount(5);
    await expect(page.getByTestId('project-timeline-pagination-state')).toContainText('Page 1 / size 5');

    await expect(page.getByTestId('project-timeline-next-page')).toBeEnabled();
    const timelinePageTwoRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'GET' &&
        networkRequest.url().includes(`/api/projects/${projectId}/timeline`) &&
        networkRequest.url().includes('page=2') &&
        networkRequest.url().includes('page_size=5'),
    );
    await page.getByTestId('project-timeline-next-page').click();
    await timelinePageTwoRequestPromise;
    await expect(page.getByTestId('project-timeline-pagination-state')).toContainText('Page 2 / size 5');
    await expect(page.getByTestId('project-timeline-prev-page')).toBeEnabled();
  });

  test('projects/:project_id archive command panel action calls archive endpoint and applies lock state', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-workspace-home-archive-command');
    const project = await createProject(request, title);
    const projectId = project.id;

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId('project-command-panel-archive-button')).toBeVisible();

    const archiveRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/archive`),
    );
    const archiveResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/archive`),
    );

    await page.getByTestId('project-command-panel-archive-button').click();
    await expect(page.getByTestId('project-archive-confirm-dialog')).toBeVisible();
    await page.getByTestId('project-archive-confirm-submit').click();
    await archiveRequestPromise;
    const archiveResponse = await archiveResponsePromise;
    expect(archiveResponse.status()).toBe(200);

    await expect(page.getByTestId('project-command-panel-required-step')).toContainText('restore');
    await expect(page.getByTestId('project-command-panel-blocked-reason')).toContainText(
      'Restore the project to continue workflow actions.',
    );
    await expect(page.getByTestId('project-command-panel-archive-button-disabled')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-open-runs-disabled')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-open-exports-disabled')).toBeVisible();
  });

  test('projects/:project_id restore command panel action calls restore endpoint and unlocks archived state', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-workspace-home-restore-command');
    const project = await createProject(request, title);
    const projectId = project.id;

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

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
    await waitForSetupCompletion(request, projectId);

    const archiveResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/archive`);
    expect(archiveResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId('project-command-panel-restore-button')).toBeVisible();

    const restoreRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/restore`),
    );
    const restoreResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/restore`),
    );

    await page.getByTestId('project-command-panel-restore-button').click();
    await expect(page.getByTestId('project-restore-confirm-dialog')).toBeVisible();
    await page.getByTestId('project-restore-confirm-submit').click();
    await restoreRequestPromise;
    const restoreResponse = await restoreResponsePromise;
    expect(restoreResponse.status()).toBe(200);

    await expect(page.getByTestId('project-command-panel-archive-button')).toBeVisible();
    await expect(page.getByTestId('project-command-panel-restore-button-disabled')).toBeVisible();
  });

  test('create draft stays setup-gated until completion, then allows overview access', async ({ page, request }) => {
    const title = uniqueTitle('e2e-draft-setup-gate');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    await page.goto(`/projects/${projectId}/overview`);
    await expect(page).toHaveURL(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'txt',
        source_filename: 'minimal-novel.txt',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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

    await waitForSetupCompletion(request, projectId);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page).toHaveURL(`/projects/${projectId}/overview`);
    await expect(page.getByTestId('project-overview-ready')).toBeVisible();
  });

  test('projects/:project_id setup source form calls ingest/source endpoint with entered metadata', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-setup-source-attach-form');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const sourceAttachRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/source`),
    );
    const sourceAttachResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/source`),
    );

    await page.getByTestId('project-setup-source-type-select').selectOption('markdown');
    await page.getByTestId('project-setup-source-filename-input').fill('minimal-novel.md');
    await page.getByTestId('project-setup-source-attach-submit').click();

    const sourceAttachRequest = await sourceAttachRequestPromise;
    const sourceAttachPayload = sourceAttachRequest.postDataJSON() as {
      source: string;
      source_filename: string;
    };
    expect(sourceAttachPayload.source).toBe('markdown');
    expect(sourceAttachPayload.source_filename).toBe('minimal-novel.md');

    const sourceAttachResponse = await sourceAttachResponsePromise;
    expect(sourceAttachResponse.status()).toBe(200);
  });

  test('projects/:project_id setup txt ingestion form calls ingest/txt endpoint', async ({ page, request }) => {
    const title = uniqueTitle('e2e-setup-txt-ingestion-form');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'txt',
        source_filename: 'minimal-novel.txt',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const txtIngestRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/txt`),
    );
    const txtIngestResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/txt`),
    );

    await page.getByTestId('project-setup-ingestion-file-input').setInputFiles(fixtureNovelPath);
    await page.getByTestId('project-setup-ingestion-submit').click();

    await txtIngestRequestPromise;
    const txtIngestResponse = await txtIngestResponsePromise;
    expect(txtIngestResponse.status()).toBe(200);
    await expect(page.getByTestId('project-setup-ingestion-output-summary')).toBeVisible();
    await expect(page.getByTestId('project-setup-ingestion-output-source')).toContainText('TXT');
    await expect(page.getByTestId('project-setup-normalization-summary')).toBeVisible();
    await expect(page.getByTestId('project-setup-ingestion-output-chapter-count')).toContainText('Chapters detected:');
    await expect(page.getByTestId('project-setup-ingestion-output-warning-count')).toContainText('Warnings:');
  });

  test('projects/:project_id setup markdown ingestion form calls ingest/markdown endpoint', async ({ page, request }) => {
    const title = uniqueTitle('e2e-setup-markdown-ingestion-form');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'markdown',
        source_filename: 'minimal-novel.md',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const markdownIngestRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/markdown`),
    );
    const markdownIngestResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/markdown`),
    );

    await page.getByTestId('project-setup-markdown-ingestion-file-input').setInputFiles({
      name: 'minimal-novel.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# Chapter 1\n\nMarkdown ingestion body.'),
    });
    await page.getByTestId('project-setup-markdown-ingestion-submit').click();

    await markdownIngestRequestPromise;
    const markdownIngestResponse = await markdownIngestResponsePromise;
    expect(markdownIngestResponse.status()).toBe(200);
  });

  test('projects/:project_id setup shows unsupported-file error and retry for markdown ingestion failures', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-setup-markdown-retry-error');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'markdown',
        source_filename: 'minimal-novel.md',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const firstMarkdownFailureRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/markdown`),
    );
    const firstMarkdownFailureResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/markdown`),
    );

    await page.getByTestId('project-setup-markdown-ingestion-file-input').setInputFiles({
      name: 'bad.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('wrong extension payload'),
    });
    await page.getByTestId('project-setup-markdown-ingestion-submit').click();

    await firstMarkdownFailureRequestPromise;
    const firstMarkdownFailureResponse = await firstMarkdownFailureResponsePromise;
    expect(firstMarkdownFailureResponse.status()).toBe(400);

    await expect(page.getByTestId('project-setup-ingestion-error-panel')).toBeVisible();
    await expect(page.getByTestId('project-setup-ingestion-error-kind')).toContainText('unsupported_file');
    await expect(page.getByTestId('project-setup-ingestion-retry-button')).toContainText('Retry markdown ingestion');

    const retryMarkdownFailureRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/markdown`),
    );
    const retryMarkdownFailureResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/markdown`),
    );

    await page.getByTestId('project-setup-ingestion-retry-button').click();
    await retryMarkdownFailureRequestPromise;
    const retryMarkdownFailureResponse = await retryMarkdownFailureResponsePromise;
    expect(retryMarkdownFailureResponse.status()).toBe(400);
  });

  test('projects/:project_id setup epub ingestion form calls ingest/epub endpoint', async ({ page, request }) => {
    const title = uniqueTitle('e2e-setup-epub-ingestion-form');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'epub',
        source_filename: 'minimal-novel.epub',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const epubIngestRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/epub`),
    );
    const epubIngestResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/epub`),
    );

    await page.getByTestId('project-setup-epub-ingestion-file-input').setInputFiles({
      name: 'minimal-novel.epub',
      mimeType: 'application/epub+zip',
      buffer: Buffer.from('not-a-real-epub'),
    });
    await page.getByTestId('project-setup-epub-ingestion-submit').click();

    await epubIngestRequestPromise;
    const epubIngestResponse = await epubIngestResponsePromise;
    expect([400, 501]).toContain(epubIngestResponse.status());
  });

  test('projects/:project_id setup chapter-directory form calls ingest/chapters-dir endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-setup-chapters-dir-ingestion-form');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'chapters-dir',
        source_filename: 'chapters/',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const chapterDirectoryIngestRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/chapters-dir`),
    );
    const chapterDirectoryIngestResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/chapters-dir`),
    );

    await page.getByTestId('project-setup-chapters-dir-ingestion-files-input').setInputFiles([
      {
        name: '01.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('Chapter 1'),
      },
      {
        name: '02.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('Chapter 2'),
      },
    ]);
    await page.getByTestId('project-setup-chapters-dir-ingestion-submit').click();

    await chapterDirectoryIngestRequestPromise;
    const chapterDirectoryIngestResponse = await chapterDirectoryIngestResponsePromise;
    expect(chapterDirectoryIngestResponse.status()).toBe(200);
  });

  test('projects/:project_id setup append-chapter form calls ingest/append-chapter endpoint', async ({
    page,
    request,
  }) => {
    const title = uniqueTitle('e2e-setup-append-chapter-form');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'txt',
        source_filename: 'minimal-novel.txt',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    await page.goto(`/projects/${projectId}/setup`);
    await expect(page.getByTestId('project-setup-ready')).toBeVisible();

    const appendChapterRequestPromise = page.waitForRequest(
      (networkRequest) =>
        networkRequest.method() === 'POST' &&
        networkRequest.url().endsWith(`/api/projects/${projectId}/ingest/append-chapter`),
    );
    const appendChapterResponsePromise = page.waitForResponse(
      (networkResponse) =>
        networkResponse.request().method() === 'POST' &&
        networkResponse.url().endsWith(`/api/projects/${projectId}/ingest/append-chapter`),
    );

    await page.getByTestId('project-setup-append-chapter-file-input').setInputFiles({
      name: 'bonus-chapter.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Bonus chapter content'),
    });
    await page.getByTestId('project-setup-append-chapter-submit').click();

    await appendChapterRequestPromise;
    const appendChapterResponse = await appendChapterResponsePromise;
    expect(appendChapterResponse.status()).toBe(200);
  });

  test('locked domain route shows guard before setup and unlocks after completion', async ({ page, request }) => {
    const title = uniqueTitle('e2e-locked-domain-route');
    const createDraftResponse = await request.post(`${backendBaseUrl}/api/projects/drafts`, {
      data: {
        title,
        do_not_store_source_text: false,
      },
    });
    expect(createDraftResponse.status()).toBe(201);
    const draftPayload = (await createDraftResponse.json()) as ProjectResponse;
    const projectId = draftPayload.id;
    expect(projectId).toBeGreaterThan(0);

    const attachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
      data: {
        source: 'txt',
        source_filename: 'minimal-novel.txt',
      },
    });
    expect(attachSourceResponse.status()).toBe(200);

    const txtIngestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: createReadStream(fixtureNovelPath),
      },
    });
    expect(txtIngestResponse.status()).toBe(200);

    const modeSwitchResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
      data: { mode: 'author' },
    });
    expect(modeSwitchResponse.status()).toBe(200);

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

    await waitForSetupCompletion(request, projectId);

    const archiveResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/archive`);
    expect(archiveResponse.status()).toBe(200);
    const archivePayload = (await archiveResponse.json()) as ProjectLifecycleStateChangeResponse;
    expect(archivePayload.action).toBe('archive');
    expect(archivePayload.lifecycle_state).toBe('archived');
    expect(archivePayload.allowed_actions).toEqual(['restore']);

    await page.goto(`/projects/${projectId}/exports`);
    await expect(page).toHaveURL(`/projects/${projectId}/exports`);
    await expect(page.getByTestId('project-workspace-deep-link-guard')).toBeVisible();
    await expect(page.getByTestId('project-workspace-deep-link-guard-action')).toBeVisible();
    await page.getByTestId('project-workspace-deep-link-guard-action').click();
    await expect(page).toHaveURL(`/projects/${projectId}/overview`);

    const restoreResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/restore`);
    expect(restoreResponse.status()).toBe(200);
    const restorePayload = (await restoreResponse.json()) as ProjectLifecycleStateChangeResponse;
    expect(restorePayload.action).toBe('restore');

    const restoredSetupStatusResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/setup-status`);
    expect(restoredSetupStatusResponse.status()).toBe(200);
    const restoredSetupStatusPayload = (await restoredSetupStatusResponse.json()) as ProjectSetupStatusResponse;

    if (!restoredSetupStatusPayload.is_complete) {
      const reattachSourceResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/source`, {
        data: {
          source: 'txt',
          source_filename: 'minimal-novel.txt',
        },
      });
      expect([200, 400, 409]).toContain(reattachSourceResponse.status());

      const reingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
        multipart: {
          file: createReadStream(fixtureNovelPath),
        },
      });
      expect(reingestResponse.status()).toBe(200);

      const remodeResponse = await request.put(`${backendBaseUrl}/api/projects/${projectId}/mode`, {
        data: { mode: 'author' },
      });
      expect(remodeResponse.status()).toBe(200);

      const rerunResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
        data: {
          mode: 'author',
          max_segment_chars: 140,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          allow_unfinalized_character_map: true,
        },
      });
      expect(rerunResponse.status()).toBe(200);

      await waitForSetupCompletion(request, projectId);
    }

    await page.goto(`/projects/${projectId}/exports`);
    await expect(page).toHaveURL(`/projects/${projectId}/exports`);
    await expect(page.getByTestId('project-workspace-deep-link-guard')).toHaveCount(0);
    await expect(page.getByText('Export Package')).toBeVisible();
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

  test('all mode profiles can run and export against the live backend', async ({ request }) => {
    const modes = ['audiobook', 'academic', 'author', 'custom'] as const;
    const project = await createProject(request, uniqueTitle('e2e-all-mode-profiles'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'all-mode-profiles.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(
            'Chapter 1\nThe harbor lamps flickered while the crew watched the horizon.\n\n'
              + 'Chapter 2\nA warning siren echoed through the steel corridor.',
          ),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    for (const mode of modes) {
      const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
        data: {
          mode,
          max_segment_chars: mode === 'academic' ? 180 : 140,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          allow_unfinalized_character_map: true,
        },
      });
      expect(runResponse.status()).toBe(200);
      const runPayload = (await runResponse.json()) as { run_id: number; status: string; segment_count: number };
      expect(runPayload.run_id).toBeGreaterThan(0);
      expect(runPayload.status).toBe('completed');
      expect(runPayload.segment_count).toBeGreaterThan(0);

      const runDetailResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${runPayload.run_id}`);
      expect(runDetailResponse.status()).toBe(200);
      const runDetailPayload = (await runDetailResponse.json()) as {
        status: string;
        config: Record<string, unknown>;
      };
      expect(runDetailPayload.status).toBe('completed');
      expect(runDetailPayload.config.mode).toBe(mode);

      const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
      expect(exportResponse.status()).toBe(200);
      const exportPayload = (await exportResponse.json()) as {
        run_id: number;
        segments: unknown[];
        manifest: { run: { config_snapshot: { mode: string } } };
      };
      expect(exportPayload.run_id).toBe(runPayload.run_id);
      expect(exportPayload.manifest.run.config_snapshot.mode).toBe(mode);
      expect(exportPayload.segments.length).toBeGreaterThan(0);

      const academicExportResponse = await request.get(
        `${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`,
        { params: { output_schema: 'academic', output_format: 'json' } },
      );
      expect(academicExportResponse.status()).toBe(200);

      if (mode === 'author') {
        const authorExportResponse = await request.get(
          `${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`,
          { params: { output_schema: 'author' } },
        );
        expect(authorExportResponse.status()).toBe(200);
        const authorPayload = (await authorExportResponse.json()) as { output_schema: string };
        expect(authorPayload.output_schema).toBe('author_narrative_health_json');
      }
    }
  });

  test('correlation ID propagates from run API to export payload and headers', async ({ request }) => {
    const correlationId = `corr-e2e-${Date.now()}`;
    const project = await createProject(request, uniqueTitle('e2e-correlation-id'));
    const projectId = project.id;

    const ingestResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/ingest/txt`, {
      multipart: {
        file: {
          name: 'correlation-id.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('Chapter 1\nA distant bell rang while the archive doors closed.'),
        },
      },
    });
    expect(ingestResponse.status()).toBe(200);

    const runResponse = await request.post(`${backendBaseUrl}/api/projects/${projectId}/runs`, {
      data: {
        mode: 'author',
        max_segment_chars: 130,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        allow_unfinalized_character_map: true,
      },
      headers: {
        'X-Correlation-Id': correlationId,
      },
    });
    expect(runResponse.status()).toBe(200);
    const runPayload = (await runResponse.json()) as { run_id: number };

    const runDetailResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/runs/${runPayload.run_id}`);
    expect(runDetailResponse.status()).toBe(200);
    const runDetailPayload = (await runDetailResponse.json()) as { config: Record<string, unknown> };
    expect(runDetailPayload.config.correlation_id).toBe(correlationId);

    const exportResponse = await request.get(`${backendBaseUrl}/api/projects/${projectId}/exports/${runPayload.run_id}.json`);
    expect(exportResponse.status()).toBe(200);
    expect(exportResponse.headers()['x-correlation-id']).toBe(correlationId);
    const exportPayload = (await exportResponse.json()) as {
      correlation_id: string;
      manifest: {
        correlation_id: string;
        run: {
          correlation_id: string;
        };
        academic_export_manifest: {
          correlation_id: string;
        };
      };
    };
    expect(exportPayload.correlation_id).toBe(correlationId);
    expect(exportPayload.manifest.correlation_id).toBe(correlationId);
    expect(exportPayload.manifest.run.correlation_id).toBe(correlationId);
    expect(exportPayload.manifest.academic_export_manifest.correlation_id).toBe(correlationId);
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
