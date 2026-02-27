import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { MainShell } from '@/app/main-shell';

vi.mock('@/app/project-step-nav', () => ({
  ProjectStepNav: () => <nav data-testid="project-step-nav">Project nav</nav>,
}));

vi.mock('@/features/workflow/prefetch/critical-route-prefetch', () => ({
  useCriticalRoutePrefetch: () => undefined,
}));

function renderMainShell(pathname: string) {
  const router = createMemoryRouter(
    [
      {
        element: <MainShell />,
        children: [
          {
            path: '/dashboard',
            element: <div data-testid="dashboard-child">Dashboard route</div>,
          },
        ],
      },
    ],
    { initialEntries: [pathname] },
  );
  render(<RouterProvider router={router} />);
}

describe('main shell accessibility hardening', () => {
  it('renders skip link and main landmark targeting route title', async () => {
    renderMainShell('/dashboard');

    expect(await screen.findByTestId('dashboard-child')).toBeInTheDocument();

    const skipLink = screen.getByTestId('skip-to-main-link');
    expect(skipLink).toHaveAttribute('href', '#app-main-content');

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'app-main-content');
    expect(main).toHaveAttribute('aria-labelledby', 'app-route-title');
    expect(main).toHaveAttribute('tabindex', '-1');

    const routeTitle = screen.getByText('Control Panel Dashboard', {
      selector: '#app-route-title',
    });
    expect(routeTitle).toHaveAttribute('id', 'app-route-title');
  });
});
