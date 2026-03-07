import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useMutationEventBus } from '@/features/workflow/events/mutation-event-bus';
import { useCreateProjectDraftMutation } from '@/features/workflow/api/workflow-hooks';
import { nipeApiClient } from '@/services/api-client';

function DraftMutationHarness() {
  const createDraftMutation = useCreateProjectDraftMutation();
  return (
    <button
      type="button"
      onClick={() =>
        createDraftMutation
          .trigger({
            title: 'Hook Draft',
            do_not_store_source_text: false,
          })
          .catch(() => undefined)
      }
    >
      Trigger draft mutation
    </button>
  );
}

describe('workflow hooks mutation event bus integration', () => {
  beforeEach(() => {
    useMutationEventBus.getState().clear();
  });

  it('publishes a success mutation event for draft creation', async () => {
    const user = userEvent.setup();
    const createDraftSpy = vi.spyOn(nipeApiClient, 'createProjectDraft').mockResolvedValue({
      id: 311,
      title: 'Hook Draft',
      selected_mode: 'audiobook',
      selected_modes: ['audiobook'],
      llm_enabled: false,
      do_not_store_source_text: false,
      configuration_snapshot_id: 'project-311-config-initial',
      ingestion_timestamp: null,
      created_at: '2026-02-27T00:00:00Z',
    });

    render(<DraftMutationHarness />);

    await user.click(screen.getByRole('button', { name: 'Trigger draft mutation' }));

    await waitFor(() => {
      expect(createDraftSpy).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(useMutationEventBus.getState().queue).toHaveLength(1);
    });
    const latestEvent = useMutationEventBus.getState().queue[0];
    expect(latestEvent?.level).toBe('success');
    expect(latestEvent?.title).toBe('Draft project created');

    createDraftSpy.mockRestore();
  });

  it('publishes an error mutation event for draft creation failure', async () => {
    const user = userEvent.setup();
    const createDraftSpy = vi
      .spyOn(nipeApiClient, 'createProjectDraft')
      .mockRejectedValue(new Error('Backend unavailable'));

    render(<DraftMutationHarness />);

    await user.click(screen.getByRole('button', { name: 'Trigger draft mutation' }));

    await waitFor(() => {
      expect(createDraftSpy).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(useMutationEventBus.getState().queue).toHaveLength(1);
    });
    const latestEvent = useMutationEventBus.getState().queue[0];
    expect(latestEvent?.level).toBe('error');
    expect(latestEvent?.title).toBe('Draft project creation failed');

    createDraftSpy.mockRestore();
  });
});
