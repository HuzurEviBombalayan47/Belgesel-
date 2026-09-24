import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Clapperboard, RefreshCw, TriangleAlert } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatBytes } from "@/lib/format";
import { transcriptionBadge } from "@/lib/statusUI";
import type { Project, Scene, TranscriptSegment } from "@/lib/types";
import { useAudioEngine } from "@/hooks/useAudioEngine";
import Header from "@/components/Header";
import AudioTransport from "@/components/editor/AudioTransport";
import Timeline from "@/components/editor/Timeline";
import TranscriptPanel from "@/components/editor/TranscriptPanel";
import ScenesPanel from "@/components/editor/ScenesPanel";
import RenderDialog from "@/components/editor/RenderDialog";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [renderOpen, setRenderOpen] = useState(false);

  const projectQuery = useQuery({
    queryKey: ["project", id],
    queryFn: () => apiGet<Project>(`/projects/${id}`),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.transcription.status;
      // keep polling while the background worker is still running
      return status === "pending" || status === "processing" ? 1500 : false;
    },
  });
  const project = projectQuery.data;
  const transcriptionState = project?.transcription.status;

  // The status is part of the key so the flip to "ready" (or "failed") triggers one
  // final fetch — the worker writes the segments just before it flips the status.
  const transcriptQuery = useQuery({
    queryKey: ["transcript", id, transcriptionState],
    queryFn: () => apiGet<TranscriptSegment[]>(`/projects/${id}/transcript`),
    enabled: Boolean(project),
    placeholderData: (previous) => previous, // no empty flash while re-keying
    refetchInterval:
      transcriptionState === "pending" || transcriptionState === "processing" ? 2500 : false,
  });

  const scenesQuery = useQuery({
    queryKey: ["scenes", id],
    queryFn: () => apiGet<Scene[]>(`/projects/${id}/scenes`),
    enabled: Boolean(project),
  });

  const engine = useAudioEngine(project ? `/api/projects/${project.id}/audio` : null);
  const duration = project ? (project.audio.duration_seconds ?? engine.duration ?? 0) : 0;
  const segments = useMemo(() => transcriptQuery.data ?? [], [transcriptQuery.data]);

  const activeIndex = useMemo(() => {
    if (segments.length === 0) return null;
    const index = segments.findIndex(
      (segment) => engine.currentTime >= segment.start_seconds && engine.currentTime < segment.end_seconds,
    );
    return index >= 0 ? index : null;
  }, [segments, engine.currentTime]);

  const retryTranscription = useMutation({
    mutationFn: () => apiPost<Project>(`/projects/${id}/analyze`),
    onSuccess: (updated) => {
      queryClient.setQueryData(["project", id], updated);
      void queryClient.invalidateQueries({ queryKey: ["transcript", id] });
      toast.info("Transcription restarted");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (projectQuery.isPending) {
    return (
      <div className="flex min-h-svh flex-col">
        <Header />
        <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-4 px-4 py-6 sm:px-6" data-testid="editor-loading">
          <div className="h-8 w-64 animate-pulse rounded-md bg-muted" />
          <div className="h-20 animate-pulse rounded-xl border border-border bg-card/60" />
          <div className="h-[300px] animate-pulse rounded-xl border border-border bg-card/60" />
        </main>
      </div>
    );
  }

  if (projectQuery.isError || !project) {
    const notFound = projectQuery.error instanceof Error && "status" in projectQuery.error && (projectQuery.error as { status: number }).status === 404;
    return (
      <div className="flex min-h-svh flex-col">
        <Header />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-10 sm:px-6">
          <Card className="mx-auto max-w-md border-border bg-card" data-testid="editor-error">
            <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
              <TriangleAlert className="size-6 text-amber-300" />
              <h1 className="font-heading text-lg font-semibold text-foreground" data-testid="editor-error-title">
                {notFound ? "Project not found" : "Something went wrong"}
              </h1>
              <p className="text-sm text-muted-foreground">{errorMessage(projectQuery.error)}</p>
              <Link to="/" data-testid="editor-error-back-link" className={buttonVariants({ variant: "outline", size: "sm" })}>
                <ArrowLeft className="size-4" />
                Back to projects
              </Link>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  const transcription = transcriptionBadge(project.transcription.status);

  return (
    <div className="flex min-h-svh flex-col">
      <Header />
      <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-4 px-4 py-6 sm:px-6" data-testid="editor-page">
        {/* subheader */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Link
              to="/"
              data-testid="back-to-projects-link"
              aria-label="Back to projects"
              className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
            >
              <ArrowLeft className="size-4" />
            </Link>
            <div>
              <h1 className="font-heading text-xl font-semibold tracking-tight text-foreground" data-testid="project-title">
                {project.title}
              </h1>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <Badge
                  variant="outline"
                  className="border-emerald-500/40 font-mono text-[10px] uppercase tracking-wider text-emerald-300"
                  data-testid="project-status-badge"
                >
                  audio in R2
                </Badge>
                <span
                  className={badgeVariants({
                    variant: "outline",
                    className: `font-mono text-[10px] uppercase tracking-wider ${transcription.className}`,
                  })}
                  data-testid="transcription-status-badge"
                >
                  {transcription.label}
                </span>
                <span className="font-mono text-[10px] tracking-wider text-muted-foreground" data-testid="project-file-meta">
                  {project.audio.file_name} · {formatBytes(project.audio.size_bytes)}
                  {project.transcription.model ? ` · ${project.transcription.model}` : ""}
                  {project.transcription.language ? ` · ${project.transcription.language}` : ""}
                </span>
              </div>
            </div>
          </div>
          <Button data-testid="render-video-button" onClick={() => setRenderOpen(true)} className="gap-2">
            <Clapperboard className="size-4" />
            Render video
          </Button>
        </div>

        {engine.error ? (
          <div
            className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-300"
            data-testid="audio-error-banner"
          >
            <TriangleAlert className="size-4 shrink-0" />
            {engine.error}
          </div>
        ) : null}

        {/* transport */}
        <Card className="border-border/80 bg-card">
          <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4">
            <AudioTransport
              playing={engine.playing}
              currentTime={engine.currentTime}
              duration={duration || engine.duration}
              onToggle={engine.toggle}
              onSkip={engine.skip}
            />
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground" data-testid="transport-hint">
              click the timeline to scrub · click a transcript row to jump
            </p>
          </CardContent>
        </Card>

        {/* timeline */}
        <Timeline
          duration={duration}
          currentTime={engine.currentTime}
          peaks={project.audio.waveform}
          segments={segments}
          scenes={scenesQuery.data ?? []}
          transcriptState={project.transcription.status}
          onSeek={engine.seek}
        />

        {/* inspectors */}
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <TranscriptPanel
              state={project.transcription.status}
              segments={segments}
              activeIndex={activeIndex}
              onSeek={engine.seek}
              onRetry={() => retryTranscription.mutate()}
              retrying={retryTranscription.isPending}
              errorText={project.transcription.error}
            />
          </div>
          <ScenesPanel scenes={scenesQuery.data ?? []} />
        </div>
      </main>

      <RenderDialog open={renderOpen} onOpenChange={setRenderOpen} />
    </div>
  );
}
