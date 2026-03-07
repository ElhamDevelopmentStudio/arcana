import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { WorkflowPageShell } from '@/app/workflow-page-shell';

describe('workflow page shell accessibility', () => {
  it('associates section landmark with the page heading', () => {
    render(
      <WorkflowPageShell description="Monitor active run lifecycle and outputs." step="Step 05" title="Run Monitor">
        <div>Body content</div>
      </WorkflowPageShell>,
    );

    const heading = screen.getByRole('heading', { name: 'Run Monitor' });
    const section = heading.closest('section');

    expect(heading.id.length).toBeGreaterThan(0);
    expect(section).toHaveAttribute('aria-labelledby', heading.id);
  });

  it('renders probabilistic output disclaimer with alert semantics when enabled', () => {
    render(
      <WorkflowPageShell
        description="Export selected run artifacts."
        showOutputDisclaimer
        step="Step 06"
        title="Export Delivery"
      >
        <div>Export content</div>
      </WorkflowPageShell>,
    );

    expect(screen.getByTestId('output-probabilistic-disclaimer')).toBeInTheDocument();
    expect(screen.getByText('AI outputs are probabilistic, not perfect')).toBeInTheDocument();
  });
});
