import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectSettingsPage } from '@/pages/projects/project-settings-page';
import { resetWorkspaceStore } from '../vitest/workspace-store-test-utils';

const useProjectLLMSettingsQueryMock = vi.fn();
const useUpdateProjectLLMSettingsMutationMock = vi.fn();
const updateProjectLLMSettingsTriggerMock = vi.fn();

vi.mock('@/features/workflow/api/workflow-hooks', () => ({
  useProjectLLMSettingsQuery: (...args: Parameters<typeof useProjectLLMSettingsQueryMock>) =>
    useProjectLLMSettingsQueryMock(...args),
  useUpdateProjectLLMSettingsMutation: (...args: Parameters<typeof useUpdateProjectLLMSettingsMutationMock>) =>
    useUpdateProjectLLMSettingsMutationMock(...args),
}));

function renderProjectSettingsPage() {
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:project_id/settings',
        element: <ProjectSettingsPage />,
      },
    ],
    { initialEntries: ['/projects/77/settings'] },
  );

  render(<RouterProvider router={router} />);
}

describe('project settings page', () => {
  beforeEach(() => {
    resetWorkspaceStore();
    useProjectLLMSettingsQueryMock.mockReset();
    useUpdateProjectLLMSettingsMutationMock.mockReset();
    updateProjectLLMSettingsTriggerMock.mockReset();

    useProjectLLMSettingsQueryMock.mockReturnValue({
      isLoading: false,
      error: undefined,
      data: {
        project_id: 77,
        llm_enabled: false,
      },
    });
    useUpdateProjectLLMSettingsMutationMock.mockReturnValue({
      isMutating: false,
      trigger: updateProjectLLMSettingsTriggerMock,
    });
  });

  it('renders loading state while project LLM settings query is pending', () => {
    useProjectLLMSettingsQueryMock.mockReturnValue({
      isLoading: true,
      error: undefined,
      data: undefined,
    });

    renderProjectSettingsPage();

    expect(screen.getByTestId('project-settings-llm-loading')).toBeInTheDocument();
  });

  it('updates project LLM setting through save action', async () => {
    const user = userEvent.setup();
    updateProjectLLMSettingsTriggerMock.mockResolvedValue({
      project_id: 77,
      llm_enabled: true,
    });

    renderProjectSettingsPage();

    const saveButton = screen.getByTestId('project-settings-llm-save');
    expect(saveButton).toBeDisabled();
    expect(screen.getByTestId('project-settings-llm-current')).toHaveTextContent('disabled');

    await user.click(screen.getByTestId('project-settings-llm-toggle'));
    expect(screen.getByTestId('project-settings-llm-draft')).toHaveTextContent('enabled');
    expect(saveButton).toBeEnabled();

    await user.click(saveButton);
    expect(updateProjectLLMSettingsTriggerMock).toHaveBeenCalledWith({ llm_enabled: true });
  });
});
