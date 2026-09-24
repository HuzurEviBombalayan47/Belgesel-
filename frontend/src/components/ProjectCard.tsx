import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUpRight, Loader2, Trash2 } from "lucide-react";
import { apiDelete } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatBytes, formatDate, formatDurationLabel } from "@/lib/format";
import { transcriptionBadge } from "@/lib/statusUI";
import type { ProjectSummary } from "@/lib/types";
import { badgeVariants } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export default function ProjectCard({ project }: { project: ProjectSummary }) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const del = useMutation({
    mutationFn: () => apiDelete<{ ok: boolean }>(`/projects/${project.id}`),
    onSuccess: () => {
      toast.success("Project deleted");
      setConfirmOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const transcription = transcriptionBadge(project.transcription_status);

  return (
    <Card
      data-testid="project-card"
      className="flex flex-col border-border/80 bg-card transition-colors duration-200 hover:border-gold/40"
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="font-heading text-base leading-snug text-foreground" data-testid="project-title">
            {project.title}
          </CardTitle>
          <span
            className={badgeVariants({
              variant: "outline",
              className: `shrink-0 font-mono text-[10px] uppercase tracking-wider ${transcription.className}`,
            })}
            data-testid="project-transcription-badge"
          >
            {transcription.label}
          </span>
        </div>
        {project.scene_count > 0 ? (
          <span
            className={badgeVariants({
              variant: "outline",
              className:
                "mt-2 w-fit border-gold/40 font-mono text-[10px] uppercase tracking-wider text-amber-200",
            })}
            data-testid="project-scene-badge"
          >
            {project.scene_count} scenes planned
          </span>
        ) : null}
      </CardHeader>
      <CardContent className="flex-1 pb-4">
        <dl className="grid grid-cols-3 gap-2 font-mono text-xs text-muted-foreground">
          <div>
            <dt className="text-[10px] uppercase tracking-wider">Length</dt>
            <dd className="mt-0.5 text-foreground" data-testid="project-duration">
              {formatDurationLabel(project.duration_seconds)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider">Size</dt>
            <dd className="mt-0.5 text-foreground">{formatBytes(project.size_bytes)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider">Created</dt>
            <dd className="mt-0.5 text-foreground">{formatDate(project.created_at)}</dd>
          </div>
        </dl>
      </CardContent>
      <CardFooter className="justify-between gap-2 border-t border-border/60 pt-4">
        <Link
          to={`/projects/${project.id}`}
          data-testid="project-open-button"
          className={buttonVariants({ variant: "secondary", size: "sm" })}
        >
          Open editor
          <ArrowUpRight className="size-3.5" />
        </Link>
        <Button
          variant="ghost"
          size="icon-sm"
          data-testid="project-delete-button"
          aria-label={`Delete ${project.title}`}
          onClick={() => setConfirmOpen(true)}
          className="text-muted-foreground hover:text-red-300"
        >
          <Trash2 className="size-4" />
        </Button>
      </CardFooter>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-w-md border-border bg-card">
          <DialogHeader>
            <DialogTitle className="font-heading">Delete “{project.title}”?</DialogTitle>
            <DialogDescription>
              The narration is removed from your R2 bucket along with its transcript. This
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setConfirmOpen(false)} data-testid="project-delete-cancel-button">
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              data-testid="project-delete-confirm-button"
              disabled={del.isPending}
              onClick={() => del.mutate()}
            >
              {del.isPending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              Delete project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
