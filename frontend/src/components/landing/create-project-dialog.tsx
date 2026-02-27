import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useCreateProjectDraftMutation } from '@/features/workflow/api/workflow-hooks';

type CreateProjectDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function CreateProjectDialog({ open, onOpenChange }: CreateProjectDialogProps) {
  const navigate = useNavigate();
  const setProject = useWorkspaceStore((state) => state.setProject);
  const [projectName, setProjectName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const createDraftMutation = useCreateProjectDraftMutation();

  const isLoading = createDraftMutation.isMutating;

  async function handleCreateProject() {
    if (!projectName.trim()) {
      setError('Project name is required.');
      return;
    }

    setError(null);
    try {
      const project = await createDraftMutation.trigger({
        title: projectName.trim(),
        do_not_store_source_text: false,
      });
      setProject({
        projectId: project.id,
        projectTitle: project.title,
        selectedMode: null,
      });
      onOpenChange(false);
      setProjectName('');
      navigate('/projects/new');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to create project.');
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Draft Project</DialogTitle>
          <DialogDescription>
            Create a draft now and continue with ingestion later in the project workflow.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Input
            data-testid="landing-create-project-input"
            disabled={isLoading}
            onChange={(event) => setProjectName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void handleCreateProject();
              }
            }}
            placeholder="Project name"
            value={projectName}
          />
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="flex justify-end gap-2">
            <Button disabled={isLoading} onClick={() => onOpenChange(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button
              data-testid="landing-create-project-submit"
              disabled={isLoading || projectName.trim().length === 0}
              onClick={() => void handleCreateProject()}
              type="button"
            >
              {isLoading ? 'Creating...' : 'Create Draft'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

