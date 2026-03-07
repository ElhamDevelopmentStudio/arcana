import { formatDistanceToNow } from 'date-fns';
import { Archive } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ProjectControlPanelProjectListItemDto } from '@/app/schemas/api';

const MODE_LABELS: Record<string, string> = {
  audiobook: 'Audiobook',
  academic: 'Academic',
  author: 'Author',
  custom: 'Custom',
};

type StatusInfo = {
  dot: string;
  label: string;
};

function resolveStatus(item: ProjectControlPanelProjectListItemDto): StatusInfo {
  if (item.last_run_status === 'running' || item.last_run_status === 'queued') {
    return { dot: 'bg-amber-400', label: 'Run in progress' };
  }
  if (item.last_run_status === 'failed') {
    return { dot: 'bg-red-400', label: 'Last run failed' };
  }
  if (item.last_run_status === 'completed') {
    return { dot: 'bg-green-400', label: 'Last run succeeded' };
  }
  return { dot: 'bg-white/20', label: 'No runs yet' };
}

type ProjectCardProps = {
  item: ProjectControlPanelProjectListItemDto;
  onClick: () => void;
  onArchive?: () => void;
};

export function ProjectCard({ item, onClick, onArchive }: ProjectCardProps) {
  const status = resolveStatus(item);
  const modeLabel = item.selected_mode ? (MODE_LABELS[item.selected_mode] ?? item.selected_mode) : 'No mode';
  const updatedAt = item.updated_at
    ? formatDistanceToNow(new Date(item.updated_at), { addSuffix: true })
    : null;

  return (
    <button
      className={cn(
        'group relative flex w-full cursor-pointer flex-col gap-3 rounded-xl border border-white/10 bg-card p-4 text-left transition-all duration-150',
        'hover:border-white/20 hover:shadow-lg hover:shadow-black/20',
      )}
      data-testid={`project-card-${item.project_id}`}
      onClick={onClick}
      type="button"
    >
      {/* Archive button on hover */}
      {onArchive ? (
        <button
          aria-label="Archive project"
          className="absolute right-3 top-3 hidden rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground group-hover:flex"
          onClick={(e) => {
            e.stopPropagation();
            onArchive();
          }}
          type="button"
        >
          <Archive size={13} />
        </button>
      ) : null}

      {/* Project name */}
      <p className="truncate pr-6 text-sm font-semibold text-foreground">
        {item.project_id ? `Project #${item.project_id}` : 'Untitled Project'}
      </p>

      {/* Mode badge */}
      <span className="inline-flex w-fit rounded-full border border-white/10 px-2 py-0.5 text-xs text-muted-foreground">
        {modeLabel}
      </span>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span className={cn('size-1.5 shrink-0 rounded-full', status.dot)} />
        <span className="text-xs text-muted-foreground">{status.label}</span>
      </div>

      {/* Date */}
      {updatedAt ? (
        <p className="mt-auto text-xs text-muted-foreground/60">Updated {updatedAt}</p>
      ) : null}
    </button>
  );
}
