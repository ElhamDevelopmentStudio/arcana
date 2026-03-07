import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { ProjectDashboardsPage } from '@/pages/projects/project-dashboards-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useExportPayloadQuery: () => ({
    data: {
      project_id: 202,
      project_title: 'Arcane Tension Project',
      run_id: 88,
      status: 'complete',
      segments: [
        {
          segment_id: '202-001',
          chapter_id: 1,
          segment_index: 1,
          tension_contribution: { value: 0.1 },
        },
        {
          segment_id: '202-002',
          chapter_id: 1,
          segment_index: 2,
          tension_contribution: { value: 0.2 },
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
  useTensionGraphQuery: () => ({
    data: {
      metric_id: 'smoothed_tension_curve',
      metric_label: 'Smoothed tension curve',
      source_path: ['smoothed_tension_curve', 'tension_curve'],
      value_key: 'smoothed_tension',
      points: [
        { position: 1, smoothed_tension: 0.25, segment_id: '202-001' },
        { position: 2, smoothed_tension: 0.35, segment_id: '202-002' },
      ],
      peak_markers: [
        {
          position: 2,
          segment_id: '202-002',
          peak_type: 'minor',
          severity: 'major',
          prominence: 0.22,
          previous_tension: 0.18,
          next_tension: 0.33,
          tension_value: 0.35,
        },
      ],
      plateau_regions: [
        {
          region_type: 'local_flatline',
          start_position: 1,
          end_position: 2,
          length: 2,
          segment_count: 2,
          segment_ids: ['202-001', '202-002'],
          segment_indices: [1, 2],
          chapter_ids: [1, 1],
          average_tension: 0.3,
          tension_value_range: {
            min: 0.24,
            max: 0.36,
            delta: 0.12,
          },
        },
      ],
      metadata: {},
    },
    isLoading: false,
    error: null,
  }),
  useCharacterAnalyticsQuery: () => ({
    data: {
      project_id: 202,
      run_id: 88,
      character_mentions_by_chapter: [
        {
          chapter_index: 1,
          mention_counts: {
            Aya: 4,
            Ben: 2,
            "Captain Pike": 1,
          },
        },
        {
          chapter_index: 2,
          mention_counts: {
            Aya: 1,
            Ben: 4,
          },
        },
      ],
      character_first_appearance_chapter_index: {
        Aya: 1,
        Ben: 1,
        'Captain Pike': 1,
      },
      character_last_appearance_chapter_index: {
        Aya: 2,
        Ben: 2,
        'Captain Pike': 1,
      },
      character_mentions_per_1000_words: {
        Aya: 12.3,
        Ben: 9.7,
        'Captain Pike': 4.2,
      },
      character_dialogue_line_counts: {
        Aya: 8,
        Ben: 4,
        'Captain Pike': 0,
      },
    },
    isLoading: false,
    error: null,
  }),
  useCharacterCooccurrenceGraphQuery: () => ({
    data: {
      schema_version: '1.0.0',
      output_schema: 'graph_json',
      output_format: 'graph_json',
      output_id: 'AO-004',
      output_name: 'character_cooccurrence_graph',
      project_id: 202,
      run_id: 88,
      run_status: 'complete',
      generated_at: '2025-01-01T00:00:00Z',
      generated_by: 'build_run_export_graph_json',
      graph: {
        nodes: [
          {
            character_key: 'aya',
            character_label: 'Aya',
            speaker_id: 1,
            segment_count: 5,
            chapter_ids: [1, 2],
            chapter_count: 2,
            adjacency_weight: 4,
          },
          {
            character_key: 'ben',
            character_label: 'Ben',
            speaker_id: 2,
            segment_count: 6,
            chapter_ids: [1],
            chapter_count: 1,
            adjacency_weight: 4,
          },
        ],
        edges: [
          {
            source: 'aya',
            target: 'ben',
            co_occurrence_count: 4,
            weight: 4,
            chapter_ids: [1, 2],
            chapter_count: 2,
          },
        ],
        metadata: {
          node_count: 2,
          edge_count: 1,
          scope: 'adjacent_speaker_transitions_within_chapter',
          undirected: true,
          generated_by: 'export_academic_graph',
        },
      },
      character_cooccurrence_centrality: {
        metrics_table: [
          {
            character_key: 'aya',
            character_label: 'Aya',
            speaker_id: 1,
            rank: 1,
            degree: 1,
            weighted_degree: 4,
            degree_centrality: 1,
            weighted_degree_centrality: 1,
            closeness_centrality: 0.75,
            betweenness_centrality: 0.2,
          },
          {
            character_key: 'ben',
            character_label: 'Ben',
            speaker_id: 2,
            rank: 2,
            degree: 1,
            weighted_degree: 4,
            degree_centrality: 0.8,
            weighted_degree_centrality: 0.8,
            closeness_centrality: 0.68,
            betweenness_centrality: 0.15,
          },
        ],
        metadata: {
          node_count: 2,
          edge_count: 1,
          distance_transform: 'inverse_weight',
          generated_by: 'export_academic_centrality',
          centrality_metrics: [
            'degree',
            'degree_centrality',
            'weighted_degree',
            'weighted_degree_centrality',
            'closeness_centrality',
            'betweenness_centrality',
          ],
        },
      },
      manifest_snapshot: {
        output_schema: 'academic_json',
        generated_by: 'export_academic_json',
        generated_at: '2025-01-01T00:00:00Z',
      },
    },
    isLoading: false,
    error: null,
  }),
  useAudiobookPrepDashboardQuery: () => ({
    data: {
      schema_version: '1.0.0',
      output_schema: 'audiobook_prep_dashboard_json',
      output_format: 'json',
      output_id: 'AB-001',
      output_name: 'audiobook_prep_dashboard',
      project_id: 202,
      run_id: 88,
      run_status: 'completed',
      generated_at: '2025-01-01T00:00:00Z',
      generated_by: 'build_audiobook_prep_dashboard',
      unresolved_speaker_count: 3,
      unresolved_voice_mapping_count: 1,
      low_confidence_region_count: 0,
      export_readiness: {
        is_ready: false,
        blocking_reasons: ['Some speaker assignments are still unresolved.'],
        warning_reasons: ['Some regions were tagged as low confidence and should be reviewed.'],
      },
    },
    isLoading: false,
    error: null,
  }),
  usePipelineStageDurationsDashboardQuery: () => ({
    data: {
      schema_version: '1.0.0',
      output_schema: 'pipeline_stage_durations_dashboard_json',
      output_format: 'json',
      output_id: 'OBS-001',
      output_name: 'pipeline_stage_durations_dashboard',
      project_id: 202,
      run_id: 88,
      run_status: 'completed',
      generated_at: '2025-01-01T00:00:00Z',
      generated_by: 'build_pipeline_stage_durations_dashboard',
      total_duration_ms: 1400,
      stage_count: 2,
      slowest_stage_name: 'merge_segment_payloads',
      slowest_stage_duration_ms: 800,
      stages: [
        {
          stage_name: 'load_and_validate_source_data',
          duration_ms: 600,
          memory_bytes_start: 1000,
          memory_bytes_end: 1200,
          memory_bytes_delta: 200,
          share_of_total: 0.428571,
        },
        {
          stage_name: 'merge_segment_payloads',
          duration_ms: 800,
          memory_bytes_start: 1200,
          memory_bytes_end: 1500,
          memory_bytes_delta: 300,
          share_of_total: 0.571429,
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

function renderDashboardPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/dashboards',
        element: <ProjectDashboardsPage />,
      },
    ],
    { initialEntries: ['/projects/202/dashboards'] },
  );
  return render(<RouterProvider router={router} />);
}

describe('project dashboards page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useWorkspaceStore.setState({
      projectId: 202,
      projectTitle: 'Arcane Tension Project',
      selectedMode: null,
      chapterCount: null,
      runId: 88,
    });
  });

  it('renders smoothed and raw tension series with a mode toggle', async () => {
    const user = userEvent.setup();
    const { container } = renderDashboardPage();

    expect(screen.getByText('Data source: run tension graph endpoint')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /tension smoothing toggle/i })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('dashboards-tension-202-001')).toHaveTextContent('T 25%');
    expect(screen.getByText('Peak markers')).toBeInTheDocument();
    expect(screen.getByText('Plateau overlays')).toBeInTheDocument();
    expect(screen.getByText('202-002: minor (major) at 35%')).toBeInTheDocument();
    expect(screen.getByText('local_flatline: S 1 to S 2 (30%)')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="tension-peak-marker-202-002"]')).toBeInTheDocument();

    await user.click(screen.getByRole('switch', { name: /tension smoothing toggle/i }));

    expect(screen.getByRole('switch', { name: /tension smoothing toggle/i })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByText('Data source: raw segment tension')).toBeInTheDocument();
    expect(screen.getByTestId('dashboards-tension-202-001')).toHaveTextContent('T 10%');
  });

  it('renders unresolved speaker count on audiobook prep summary', () => {
    renderDashboardPage();

    expect(screen.getByText('Audiobook Prep Readiness')).toBeInTheDocument();
    expect(screen.getByTestId('dashboards-audiobook-readiness-status')).toHaveTextContent('Export readiness: Not ready');
    expect(screen.getByTestId('dashboards-audiobook-unresolved-speakers')).toHaveTextContent('Unresolved speaker assignments: 3');
    expect(screen.getByTestId('dashboards-audiobook-unresolved-voice-maps')).toHaveTextContent('Unresolved voice mappings: 1');
    expect(screen.getByTestId('dashboards-audiobook-low-confidence-regions')).toHaveTextContent('Low-confidence region count: 0');
    expect(screen.getByTestId('dashboards-audiobook-blocking-reasons')).toHaveTextContent('Some speaker assignments are still unresolved.');
    expect(screen.getByTestId('dashboards-audiobook-warning-reasons')).toHaveTextContent(
      'Some regions were tagged as low confidence and should be reviewed.',
    );
  });

  it('renders pipeline stage durations dashboard using stage telemetry', () => {
    renderDashboardPage();

    expect(screen.getByText('Pipeline Stage Durations')).toBeInTheDocument();
    expect(screen.getByTestId('dashboards-stage-duration-total')).toHaveTextContent('Total pipeline time: 1400 ms');
    expect(screen.getByTestId('dashboards-stage-duration-slowest')).toHaveTextContent(
      'Slowest stage: merge_segment_payloads (800 ms)',
    );
    expect(screen.getByTestId('dashboards-stage-duration-load_and_validate_source_data')).toHaveTextContent(
      'load_and_validate_source_data',
    );
    expect(screen.getByTestId('dashboards-stage-duration-merge_segment_payloads')).toHaveTextContent(
      'merge_segment_payloads',
    );
  });

  it('renders character prominence and trend widgets from analytics endpoint data', () => {
    renderDashboardPage();

    expect(screen.getByText('Character Prominence')).toBeInTheDocument();
    const ayaProminenceRow = screen.getByTestId('dashboards-character-prominence-Aya');
    expect(ayaProminenceRow).toBeInTheDocument();
    expect(screen.getByText('Prominence: 12.30')).toBeInTheDocument();
    expect(ayaProminenceRow).toHaveTextContent(/Total mentions:\s*5/);
    expect(ayaProminenceRow).toHaveTextContent(/Dialogue lines:\s*8/);

    expect(screen.getByText('Character Mention Trends')).toBeInTheDocument();
    expect(screen.getByText('Per-chapter mention trajectory for top characters.')).toBeInTheDocument();
    expect(screen.getByText('Aya: first appears in chapter 1, last appears in chapter 2.')).toBeInTheDocument();
  });

  it('renders character co-occurrence graph cards and edge insights from co-occurrence endpoint data', () => {
    renderDashboardPage();

    expect(screen.getByText('Character Co-occurrence Graph')).toBeInTheDocument();
    expect(screen.getByTestId('dashboards-cooccurrence-node-count')).toHaveTextContent('2');
    expect(screen.getByTestId('dashboards-cooccurrence-edge-count')).toHaveTextContent('1');
    const cards = screen.getAllByText(/Top centrality rows|No centrality values available for this run\./);
    expect(cards).toHaveLength(1);

    const ayaCentralityRow = screen.getByTestId('dashboards-cooccurrence-centrality-aya');
    expect(ayaCentralityRow).toBeInTheDocument();
    expect(ayaCentralityRow).toHaveTextContent('Aya');
    expect(ayaCentralityRow).toHaveTextContent('Degree: 1');

    const ayaBenEdge = screen.getByTestId('dashboards-cooccurrence-edge-aya-ben');
    expect(ayaBenEdge).toHaveTextContent('aya ↔ ben');
    expect(ayaBenEdge).toHaveTextContent('Count: 4');
  });

  it('exports a dashboard snapshot payload from loaded dashboard data', async () => {
    const user = userEvent.setup();
    const originalCreateElement = document.createElement.bind(document);
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;

    const createObjectURL = vi.fn(() => 'blob:dashboard-snapshot');
    const revokeObjectURL = vi.fn();
    const anchorClick = vi.fn();
    let anchorHref: string | null = null;
    let anchorDownload: string | null = null;

    URL.createObjectURL = createObjectURL as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL as typeof URL.revokeObjectURL;
    const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName === 'a') {
        const anchor = element as HTMLAnchorElement;
        vi.spyOn(anchor, 'click').mockImplementation(() => {
          anchorHref = anchor.href;
          anchorDownload = anchor.download;
          anchorClick();
        });
        return anchor;
      }
      return element;
    });

    try {
      renderDashboardPage();
      await user.click(screen.getByTestId('dashboards-snapshot-export-button'));

      expect(createObjectURL).toHaveBeenCalledTimes(1);
      const snapshotBlob = createObjectURL.mock.calls[0]?.[0];
      expect(snapshotBlob).toBeInstanceOf(Blob);
      expect(snapshotBlob).not.toBeNull();

      const snapshotData = JSON.parse(await (snapshotBlob as Blob).text());
      expect(snapshotData).toMatchObject({
        project_id: 202,
        run_id: 88,
        show_smoothed_graph: true,
        tension_graph: expect.any(Object),
        character_analytics: expect.any(Object),
        cooccurrence_graph: expect.any(Object),
        audiobook_prep_dashboard: expect.any(Object),
        pipeline_stage_durations_dashboard: expect.any(Object),
      });

      expect(snapshotData.tension_graph).toMatchObject({
        metric_id: 'smoothed_tension_curve',
        points: expect.any(Array),
      });
      expect(snapshotData.character_analytics).toMatchObject({
        project_id: 202,
        run_id: 88,
        character_first_appearance_chapter_index: expect.objectContaining({ Aya: 1 }),
      });
      expect(snapshotData.cooccurrence_graph).toMatchObject({
        project_id: 202,
        run_id: 88,
        graph: expect.objectContaining({
          metadata: expect.objectContaining({
            node_count: 2,
            edge_count: 1,
          }),
        }),
      });
      expect(snapshotData.audiobook_prep_dashboard).toMatchObject({
        unresolved_speaker_count: 3,
        export_readiness: expect.objectContaining({ is_ready: false }),
      });
      expect(snapshotData.pipeline_stage_durations_dashboard).toMatchObject({
        total_duration_ms: 1400,
        stage_count: 2,
        slowest_stage_name: 'merge_segment_payloads',
      });

      expect(anchorDownload).toBe('project-202-run-88-dashboard-snapshot.json');
      expect(anchorHref).toBe('blob:dashboard-snapshot');
      expect(anchorClick).toHaveBeenCalledTimes(1);
      expect(revokeObjectURL).toHaveBeenCalledWith('blob:dashboard-snapshot');
    } finally {
      createElementSpy.mockRestore();
      URL.createObjectURL = originalCreateObjectURL;
      URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });
});
