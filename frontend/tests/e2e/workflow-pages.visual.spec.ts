import { expect, test, type Page, type Route } from '@playwright/test';

const PROJECT_ID = 101;
const RUN_ID = 501;
const FIXED_ISO_TIMESTAMP = '2026-02-27T12:00:00.000Z';

function seedWorkspace(page: Page, selectedMode: string | null) {
  return page.addInitScript(
    (payload) => {
      window.localStorage.setItem(
        'nipe-workspace',
        JSON.stringify({
          state: payload,
          version: 0,
        }),
      );
      window.localStorage.setItem(
        'nipe-ui-route-state',
        JSON.stringify({
          state: {
            dashboardListQuery: {
              page: 1,
              page_size: 20,
            },
            lastProjectRouteById: {},
          },
          version: 0,
        }),
      );
      window.sessionStorage.removeItem('nipe-run-monitor-pending-mutation');
    },
    {
      projectId: PROJECT_ID,
      projectTitle: 'Shadow Slave PoC',
      selectedMode,
      chapterCount: 12,
      runId: RUN_ID,
    },
  );
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function buildResponseEnvelope() {
  return {
    schema_version: '1.0.0',
    output_schema: 'nipe.workflow',
    output_format: 'json',
    output_id: 'pw-028-visual',
    output_name: 'PW-028 Visual Fixture',
    generated_at: FIXED_ISO_TIMESTAMP,
    generated_by: 'playwright-visual-test',
  };
}

function buildProjectAllowedActionsResponse() {
  return {
    ...buildResponseEnvelope(),
    project_id: PROJECT_ID,
    lifecycle_state: 'completed',
    last_run_status: 'completed',
    next_required_action: 'export',
    allowed_actions: ['ingest', 'select_mode', 'configure', 'run', 'rerun', 'export', 'archive'],
    blocked_reason: null,
    required_step: null,
  };
}

function buildProjectSetupStatusResponse() {
  return {
    ...buildResponseEnvelope(),
    project_id: PROJECT_ID,
    lifecycle_state: 'completed',
    next_required_action: 'export',
    is_complete: true,
    steps: [
      { step_id: 'ingestion', label: 'Ingestion attached', ready: true, required: true },
      { step_id: 'mode_selection', label: 'Mode selected', ready: true, required: true },
      { step_id: 'initial_run', label: 'Initial run completed', ready: true, required: true },
      { step_id: 'character_mapping', label: 'Character map reviewed', ready: true, required: false },
      { step_id: 'voice_mapping', label: 'Voice mappings assigned', ready: true, required: false },
    ],
  };
}

function buildProjectDetailResponse() {
  return {
    ...buildResponseEnvelope(),
    project_id: PROJECT_ID,
    title: 'Shadow Slave PoC',
    description: 'Deterministic fixture used for PW-028 visual baselines.',
    tags: ['poc', 'visual'],
    lifecycle_state: 'completed',
    last_run_status: 'completed',
    next_required_action: 'export',
    allowed_actions: ['ingest', 'select_mode', 'configure', 'run', 'rerun', 'export', 'archive'],
    selected_mode: 'audiobook',
    selected_modes: ['audiobook'],
    llm_enabled: false,
    do_not_store_source_text: false,
    character_map_finalized: true,
    configuration_snapshot_id: 'snapshot-101',
    ingestion_timestamp: '2026-02-24T14:00:00.000Z',
    last_export_at: '2026-02-27T12:05:00.000Z',
    created_at: '2026-02-24T13:00:00.000Z',
    updated_at: FIXED_ISO_TIMESTAMP,
  };
}

function buildRunDetailResponse() {
  return {
    run_id: RUN_ID,
    project_id: PROJECT_ID,
    status: 'completed',
    config: {
      mode: 'audiobook',
      max_segment_chars: 160,
      export_formats: ['json', 'csv'],
      llm_execution_mode: {
        mode: 'full',
        provider: 'openrouter',
      },
    },
    changelog_entries: [
      {
        id: 1,
        event_type: 'run.completed',
        event_message: 'Run completed successfully',
        event_metadata: {
          segment_count: 3,
        },
        created_at: FIXED_ISO_TIMESTAMP,
      },
    ],
    started_at: '2026-02-27T11:58:00.000Z',
    finished_at: FIXED_ISO_TIMESTAMP,
    segment_count: 3,
    llm_calls: [
      {
        id: 1,
        provider: 'openrouter',
        task_type: 'speaker_resolution',
        success: true,
        request_count: 3,
        is_cache_hit: false,
        detail: null,
        created_at: FIXED_ISO_TIMESTAMP,
      },
    ],
    llm_cache_metrics: {
      speaker_resolution: {
        hits: 1,
        misses: 2,
      },
    },
  };
}

function buildModeCatalogResponse() {
  const sharedProfile = {
    llm_enabled: false,
    export_formats: ['json', 'csv'],
    export_chunk_size: 500,
    provider_name: 'openrouter',
    max_calls_per_day: 25,
    deterministic_mode: false,
    speaker_confidence_threshold: 0.6,
    high_ambiguity_dialogue_flag_threshold: 2,
    unstable_emotion_shift_transition_threshold: 4,
    unstable_emotion_shift_density_threshold: 0.5,
    contradiction_review_required: true,
    web_scraping_enabled: false,
  };

  return {
    modes: ['audiobook', 'academic', 'author', 'custom'],
    default_mode: 'audiobook',
    persisted_in: ['projects.selected_mode', 'runs.config.mode'],
    mode_profiles: {
      audiobook: {
        ...sharedProfile,
        max_segment_chars: 160,
        profile_intent: 'TTS-ready segmentation with stable narration defaults.',
      },
      academic: {
        ...sharedProfile,
        max_segment_chars: 220,
        profile_intent: 'Longer analytical segments for aggregate comparisons.',
      },
      author: {
        ...sharedProfile,
        max_segment_chars: 180,
        profile_intent: 'Balanced segmentation for iterative narrative editing.',
      },
      custom: {
        ...sharedProfile,
        max_segment_chars: 255,
        profile_intent: 'Operator-tuned profile with configurable constraints.',
      },
    },
  };
}

function buildProjectControlPanelSummaryResponse() {
  return {
    ...buildResponseEnvelope(),
    total_projects: 1,
    project_counts_by_state: [
      { lifecycle_state: 'draft', project_count: 0 },
      { lifecycle_state: 'ingested', project_count: 0 },
      { lifecycle_state: 'configured', project_count: 0 },
      { lifecycle_state: 'running', project_count: 0 },
      { lifecycle_state: 'completed', project_count: 1 },
      { lifecycle_state: 'failed', project_count: 0 },
      { lifecycle_state: 'archived', project_count: 0 },
    ],
    active_run_count: 0,
    blocked_export_project_count: 0,
    blocked_export_run_count: 0,
    recent_failure_count: 0,
    recent_failures: [],
  };
}

function parsePositiveInteger(raw: string | null, fallback: number) {
  if (raw === null) {
    return fallback;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

function buildProjectControlPanelListResponse(requestUrl: URL) {
  return {
    ...buildResponseEnvelope(),
    total_items: 0,
    page: parsePositiveInteger(requestUrl.searchParams.get('page'), 1),
    page_size: parsePositiveInteger(requestUrl.searchParams.get('page_size'), 20),
    has_next_page: false,
    items: [],
  };
}

function buildProjectTimelineResponse(requestUrl: URL) {
  return {
    ...buildResponseEnvelope(),
    project_id: PROJECT_ID,
    total_items: 0,
    page: parsePositiveInteger(requestUrl.searchParams.get('page'), 1),
    page_size: parsePositiveInteger(requestUrl.searchParams.get('page_size'), 5),
    has_next_page: false,
    items: [],
  };
}

function buildCharacterMapResponse() {
  return {
    project_id: PROJECT_ID,
    character_map_finalized: true,
    characters: [
      {
        name: 'Sunny',
        verbalized_form: 'Sunny',
        gender: 'male',
        inferred_gender: 'male',
        inferred_confidence: 0.97,
        inferred_source_trace: [],
        voice_id: null,
        aliases: ['Sunless'],
        notes: null,
        source: 'manual',
        confidence: 0.99,
        source_trace: [],
      },
      {
        name: 'Nephis',
        verbalized_form: 'Nephis',
        gender: 'female',
        inferred_gender: 'female',
        inferred_confidence: 0.95,
        inferred_source_trace: [],
        voice_id: null,
        aliases: ['Changing Star'],
        notes: null,
        source: 'manual',
        confidence: 0.99,
        source_trace: [],
      },
    ],
  };
}

function buildCharacterGenderComparisonResponse() {
  return {
    project_id: PROJECT_ID,
    comparison_count: 2,
    contradiction_count: 0,
    comparisons: [
      {
        name: 'Sunny',
        manual_gender: 'male',
        inferred_gender: 'male',
        manual_confidence: 0.99,
        inferred_confidence: 0.97,
        comparison: 'match',
        contradiction_severity: 0,
        is_contradiction: false,
        requires_review: false,
      },
      {
        name: 'Nephis',
        manual_gender: 'female',
        inferred_gender: 'female',
        manual_confidence: 0.99,
        inferred_confidence: 0.95,
        comparison: 'match',
        contradiction_severity: 0,
        is_contradiction: false,
        requires_review: false,
      },
    ],
    warnings: [],
  };
}

function buildPronunciationDictionaryResponse(scope: string, entries: Array<{ term: string; verbalized_form: string }>) {
  return {
    project_id: PROJECT_ID,
    scope,
    entries: entries.map((entry) => ({
      ...entry,
      source: 'manual',
      confidence: 1,
    })),
  };
}

function buildAudiobookPrepDashboardResponse() {
  return {
    schema_version: '1.0.0',
    output_schema: 'nipe.audiobook_prep_dashboard',
    output_format: 'json',
    output_id: 'audiobook-prep-dashboard',
    output_name: 'Audiobook Prep Dashboard',
    project_id: PROJECT_ID,
    run_id: RUN_ID,
    run_status: 'completed',
    generated_at: FIXED_ISO_TIMESTAMP,
    generated_by: 'playwright-visual-test',
    unresolved_speaker_count: 0,
    unresolved_voice_mapping_count: 0,
    low_confidence_region_count: 1,
    export_readiness: {
      is_ready: true,
      blocking_reasons: [],
      warning_reasons: ['One low-confidence region remains for optional review.'],
    },
  };
}

function buildCharacterAnalyticsResponse() {
  return {
    project_id: PROJECT_ID,
    run_id: RUN_ID,
    character_mentions_by_chapter: [
      {
        chapter_index: 1,
        mention_counts: {
          Sunny: 14,
          Nephis: 8,
        },
      },
    ],
    character_first_appearance_chapter_index: {
      Sunny: 1,
      Nephis: 1,
    },
    character_last_appearance_chapter_index: {
      Sunny: 3,
      Nephis: 3,
    },
    character_mentions_per_1000_words: {
      Sunny: 10.8,
      Nephis: 7.2,
    },
    character_dialogue_line_counts: {
      Sunny: 26,
      Nephis: 17,
    },
  };
}

function buildCharacterCooccurrenceGraphResponse() {
  return {
    schema_version: '1.0.0',
    output_schema: 'nipe.character_cooccurrence_graph',
    output_format: 'json',
    output_id: 'character-cooccurrence-graph',
    output_name: 'Character Co-occurrence Graph',
    project_id: PROJECT_ID,
    run_id: RUN_ID,
    run_status: 'completed',
    generated_at: FIXED_ISO_TIMESTAMP,
    generated_by: 'playwright-visual-test',
    graph: {
      nodes: [
        {
          character_key: 'sunny',
          character_label: 'Sunny',
          speaker_id: null,
          segment_count: 9,
          chapter_ids: [1, 2, 3],
          chapter_count: 3,
          adjacency_weight: 5,
        },
        {
          character_key: 'nephis',
          character_label: 'Nephis',
          speaker_id: null,
          segment_count: 6,
          chapter_ids: [1, 2, 3],
          chapter_count: 3,
          adjacency_weight: 5,
        },
      ],
      edges: [
        {
          source: 'sunny',
          target: 'nephis',
          co_occurrence_count: 5,
          weight: 5,
          chapter_ids: [1, 2, 3],
          chapter_count: 3,
        },
      ],
      metadata: {
        node_count: 2,
        edge_count: 1,
        scope: 'run',
        undirected: true,
        generated_by: 'playwright-visual-test',
      },
    },
    character_cooccurrence_centrality: {
      metrics_table: [
        {
          character_key: 'sunny',
          character_label: 'Sunny',
          speaker_id: null,
          rank: 1,
          degree: 1,
          weighted_degree: 5,
          degree_centrality: 1,
          weighted_degree_centrality: 1,
          closeness_centrality: 1,
          betweenness_centrality: 0,
        },
      ],
      metadata: {
        node_count: 2,
        edge_count: 1,
        distance_transform: null,
        generated_by: 'playwright-visual-test',
        centrality_metrics: ['degree', 'closeness', 'betweenness'],
      },
    },
    manifest_snapshot: {
      run_id: RUN_ID,
    },
  };
}

function buildTensionGraphResponse() {
  return {
    metric_id: 'tension',
    metric_label: 'Narrative Tension',
    source_path: ['segments'],
    value_key: 'tension',
    points: [
      {
        position: 1,
        smoothed_tension: 0.42,
        chapter_id: 1,
        segment_index: 1,
        segment_id: 'seg-001',
      },
    ],
    peak_markers: [],
    plateau_regions: [],
    metadata: {
      generated_at: FIXED_ISO_TIMESTAMP,
    },
  };
}

function buildPolarityGraphResponse() {
  return {
    metric_id: 'polarity',
    metric_label: 'Polarity',
    source_path: ['segments'],
    value_key: 'rolling_mean_valence',
    points: [
      {
        position: 1,
        rolling_mean_valence: 0.11,
        rolling_mean_intensity: 0.63,
        chapter_id: 1,
        segment_index: 1,
        segment_id: 'seg-001',
      },
    ],
    volatility_markers: [],
    metadata: {
      generated_at: FIXED_ISO_TIMESTAMP,
    },
  };
}

function buildPipelineStageDurationsDashboardResponse() {
  return {
    schema_version: '1.0.0',
    output_schema: 'nipe.pipeline_stage_durations_dashboard',
    output_format: 'json',
    output_id: 'pipeline-stage-durations-dashboard',
    output_name: 'Pipeline Stage Durations Dashboard',
    project_id: PROJECT_ID,
    run_id: RUN_ID,
    run_status: 'completed',
    generated_at: FIXED_ISO_TIMESTAMP,
    generated_by: 'playwright-visual-test',
    total_duration_ms: 12840,
    stage_count: 3,
    slowest_stage_name: 'segmentation',
    slowest_stage_duration_ms: 5210,
    stages: [
      {
        stage_name: 'ingestion',
        duration_ms: 1880,
        memory_bytes_start: null,
        memory_bytes_end: null,
        memory_bytes_delta: null,
        share_of_total: 0.1464,
      },
      {
        stage_name: 'segmentation',
        duration_ms: 5210,
        memory_bytes_start: null,
        memory_bytes_end: null,
        memory_bytes_delta: null,
        share_of_total: 0.4058,
      },
      {
        stage_name: 'tagging',
        duration_ms: 5750,
        memory_bytes_start: null,
        memory_bytes_end: null,
        memory_bytes_delta: null,
        share_of_total: 0.4478,
      },
    ],
  };
}

function buildExportResponse() {
  return {
    project_id: PROJECT_ID,
    project_title: 'Shadow Slave PoC',
    run_id: RUN_ID,
    status: 'completed',
    segments: [
      {
        segment_id: 'seg-001',
        chapter_id: 1,
        confidence: {
          speaker: 0.92,
          emotion: 0.87,
          type: 0.85,
          tension: 0.79,
          dominance: 0.82,
          summary: 0.9,
        },
        tension_contribution: {
          confidence: {
            value: 0.79,
          },
        },
        dominance_contribution: {
          confidence: {
            value: 0.82,
          },
        },
        summary_tag: {
          confidence: 0.9,
        },
      },
    ],
  };
}

async function mockWorkflowApi(page: Page) {
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;

    if (pathname === '/health') {
      await fulfillJson(route, { status: 'ok' });
      return;
    }
    if (!pathname.startsWith('/api/')) {
      await route.fallback();
      return;
    }

    const projectBase = `/api/projects/${PROJECT_ID}`;
    const runBase = `${projectBase}/runs/${RUN_ID}`;

    if (pathname === '/api/modes') {
      await fulfillJson(route, buildModeCatalogResponse());
      return;
    }
    if (pathname === '/api/dashboard/project-control-panel/summary') {
      await fulfillJson(route, buildProjectControlPanelSummaryResponse());
      return;
    }
    if (pathname === '/api/dashboard/project-control-panel/projects') {
      await fulfillJson(route, buildProjectControlPanelListResponse(url));
      return;
    }
    if (pathname === `${projectBase}/setup-status`) {
      await fulfillJson(route, buildProjectSetupStatusResponse());
      return;
    }
    if (pathname === `${projectBase}/actions`) {
      await fulfillJson(route, buildProjectAllowedActionsResponse());
      return;
    }
    if (pathname === projectBase) {
      await fulfillJson(route, buildProjectDetailResponse());
      return;
    }
    if (pathname === `${projectBase}/timeline`) {
      await fulfillJson(route, buildProjectTimelineResponse(url));
      return;
    }
    if (pathname === `${projectBase}/characters`) {
      await fulfillJson(route, buildCharacterMapResponse());
      return;
    }
    if (pathname === `${projectBase}/characters/gender-comparison`) {
      await fulfillJson(route, buildCharacterGenderComparisonResponse());
      return;
    }
    if (pathname === `${projectBase}/characters/alias-collisions`) {
      await fulfillJson(route, {
        project_id: PROJECT_ID,
        collisions: [],
      });
      return;
    }
    if (pathname === `${projectBase}/pronunciation-dictionary/artifacts`) {
      await fulfillJson(
        route,
        buildPronunciationDictionaryResponse('artifacts', [{ term: 'Membrane', verbalized_form: 'mem-brane' }]),
      );
      return;
    }
    if (pathname === `${projectBase}/pronunciation-dictionary/invented`) {
      await fulfillJson(
        route,
        buildPronunciationDictionaryResponse('invented', [{ term: 'Cohort', verbalized_form: 'co-hort' }]),
      );
      return;
    }
    if (pathname === `${projectBase}/pronunciation-dictionary/global`) {
      await fulfillJson(
        route,
        buildPronunciationDictionaryResponse('global', [{ term: 'Awakened', verbalized_form: 'awakened' }]),
      );
      return;
    }
    if (pathname === `${projectBase}/pronunciation-dictionary/places`) {
      await fulfillJson(
        route,
        buildPronunciationDictionaryResponse('places', [{ term: 'NQSC', verbalized_form: 'N-Q-S-C' }]),
      );
      return;
    }
    if (pathname.startsWith(`${projectBase}/pronunciation-dictionary/character/`)) {
      const characterName = decodeURIComponent(pathname.replace(`${projectBase}/pronunciation-dictionary/character/`, ''));
      await fulfillJson(
        route,
        buildPronunciationDictionaryResponse(`character:${characterName}`, [
          { term: characterName, verbalized_form: characterName },
        ]),
      );
      return;
    }
    if (pathname === `${runBase}`) {
      await fulfillJson(route, buildRunDetailResponse());
      return;
    }
    if (pathname === `${runBase}/audiobook-prep-dashboard`) {
      await fulfillJson(route, buildAudiobookPrepDashboardResponse());
      return;
    }
    if (pathname === `${runBase}/character-analytics`) {
      await fulfillJson(route, buildCharacterAnalyticsResponse());
      return;
    }
    if (pathname === `${runBase}/character-cooccurrence-graph`) {
      await fulfillJson(route, buildCharacterCooccurrenceGraphResponse());
      return;
    }
    if (pathname === `${runBase}/tension-graph`) {
      await fulfillJson(route, buildTensionGraphResponse());
      return;
    }
    if (pathname === `${runBase}/polarity-graph`) {
      await fulfillJson(route, buildPolarityGraphResponse());
      return;
    }
    if (pathname === `${runBase}/pipeline-stage-durations-dashboard`) {
      await fulfillJson(route, buildPipelineStageDurationsDashboardResponse());
      return;
    }
    if (pathname === `${projectBase}/exports/${RUN_ID}.json`) {
      await fulfillJson(route, buildExportResponse());
      return;
    }

    await fulfillJson(route, { detail: `No mock fixture for ${pathname}` }, 404);
  });
}

async function expectVisualBaseline(
  page: Page,
  options: {
    path: string;
    selectedMode: string | null;
    readyTestId: string;
    screenshotName: string;
  },
) {
  await seedWorkspace(page, options.selectedMode);
  await page.goto(options.path);
  await expect(page.getByTestId(options.readyTestId)).toBeVisible();
  await expect(page).toHaveScreenshot(options.screenshotName, {
    fullPage: true,
    animations: 'disabled',
  });
}

test.beforeEach(async ({ page }) => {
  await mockWorkflowApi(page);
});

test('PW-028 visual baseline for landing screen', async ({ page }) => {
  await expectVisualBaseline(page, {
    path: '/',
    selectedMode: null,
    readyTestId: 'landing-enter-dashboard',
    screenshotName: 'pw028-landing.png',
  });
});

test('PW-028 visual baseline for dashboard screen', async ({ page }) => {
  await expectVisualBaseline(page, {
    path: '/dashboard',
    selectedMode: 'audiobook',
    readyTestId: 'dashboard-list-empty',
    screenshotName: 'pw028-dashboard.png',
  });
});

test('PW-028 visual baseline for project detail screen', async ({ page }) => {
  await expectVisualBaseline(page, {
    path: `/projects/${PROJECT_ID}`,
    selectedMode: 'audiobook',
    readyTestId: 'project-workspace-home-ready',
    screenshotName: 'pw028-project-detail.png',
  });
});

test('PW-028 visual baseline for ingestion screen', async ({ page }) => {
  await expectVisualBaseline(page, {
    path: '/projects/new',
    selectedMode: null,
    readyTestId: 'create-project-button',
    screenshotName: 'pw028-ingestion.png',
  });
});

test('PW-028 visual baseline for character map screen', async ({ page }) => {
  await expectVisualBaseline(page, {
    path: `/projects/${PROJECT_ID}/characters`,
    selectedMode: 'audiobook',
    readyTestId: 'character-list-state',
    screenshotName: 'pw028-character-map.png',
  });
});

test('PW-028 visual baseline for run monitor screen', async ({ page }) => {
  await expectVisualBaseline(page, {
    path: `/projects/${PROJECT_ID}/run-monitor`,
    selectedMode: 'audiobook',
    readyTestId: 'run-monitor-refresh-state',
    screenshotName: 'pw028-run-monitor.png',
  });
});

test('PW-028 visual baseline for export screen', async ({ page }) => {
  await expectVisualBaseline(page, {
    path: `/projects/${PROJECT_ID}/export`,
    selectedMode: 'audiobook',
    readyTestId: 'export-confidence-row-seg-001',
    screenshotName: 'pw028-export.png',
  });
});
