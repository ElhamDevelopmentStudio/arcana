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
});
