import { useCallback, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft,
  Clapperboard,
  Loader2,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatBytes } from "@/lib/format";
import { transcriptionBadge } from "@/lib/statusUI";
import type { Project, Scene, TranscriptSegment } from "@/lib/types";
import { useAudioEngine } from "@/hooks/useAudioEngine";
import { useSystemStatus } from "@/components/StorageBadge";
import Header from "@/components/Header";
import AudioTransport from "@/components/editor/AudioTransport";
import Timeline from "@/components/editor/Timeline";
import TranscriptPanel from "@/components/editor/TranscriptPanel";
import ScenesPanel from "@/components/editor/ScenesPanel";
import SceneInspector from "@/components/editor/SceneInspector";
import RenderDialog from "@/components/editor/RenderDialog";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [renderOpen, setRenderOpen] = useState(false);
  const [inspectedSceneId, setInspectedSceneId] = useState<string | null>(null);
  const { data: system } = useSystemStatus();

  const projectQuery = useQuery({
    queryKey: ["project", id],
    queryFn: () => apiGet<Project>(`/projects/${id}`),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const data = query.state.data;
      const transcribing =
        data?.transcription.status === "pending" || data?.transcription.status === "processing";
      const planning =
        data?.scene_planning.status === "queued" || data?.scene_planning.status === "processing";
      return transcribing || planning ? 2000 : false;
    },
  });
  const project = projectQuery.data;
  const transcriptionState = project?.transcription.status;
  const planningState = project?.scene_planning.status;

  const transcriptQuery = useQuery({
    queryKey: ["transcript", id, transcriptionState],
    queryFn: () => apiGet<TranscriptSegment[]>(`/projects/${id}/transcript`),
    enabled: Boolean(project),
    placeholderData: (previous) => previous,
    refetchInterval:
      transcriptionState === "pending" || transcriptionState === "processing" ? 2500 : false,
  });

  // Keyed on the planning status so the flip to ready/failed triggers the final fetch.
  const scenesQuery = useQuery({
    queryKey: ["scenes", id, planningState],
    queryFn: () => apiGet<Scene[]>(`/projects/${id}/scenes`),
    enabled: Boolean(project),
    placeholderData: (previous) => previous,
  });

  const engine = useAudioEngine(project ? `/api/projects/${project.id}/audio` : null);
  const duration = project ? (project.audio.duration_seconds ?? engine.duration ?? 0) : 0;
  const segments = useMemo(() => transcriptQuery.data ?? [], [transcriptQuery.data]);
  const scenes = useMemo(() => scenesQuery.data ?? [], [scenesQuery.data]);

  const activeIndex = useMemo(() => {
    if (segments.length === 0) return null;
    const index = segments.findIndex(
      (segment) => engine.currentTime >= segment.start_seconds && engine.currentTime < segment.end_seconds,
    );
    return index >= 0 ? index : null;
  }, [segments, engine.currentTime]);

  // scene under the playhead — highlighted in both the lane and the list
  const playingSceneId = useMemo(() => {
    const scene = scenes.find(
      (candidate) => engine.currentTime >= candidate.start_time && engine.currentTime < candidate.end_time,
    );
    return scene?.id ?? null;
  }, [scenes, engine.currentTime]);

  const inspectedScene = useMemo(
    () => scenes.find((scene) => scene.id === inspectedSceneId) ?? null,
    [scenes, inspectedSceneId],
  );

  const retryTranscription = useMutation({
    mutationFn: () => apiPost<Project>(`/projects/${id}/analyze`),
    onSuccess: (updated) => {
      queryClient.setQueryData(["project", id], updated);
      void queryClient.invalidateQueries({ queryKey: ["transcript", id] });
      toast.info("Transcription restarted");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const planScenes = useMutation({
    mutationFn: () => apiPost<Project>(`/projects/${id}/scenes/plan`),
    onSuccess: (updated) => {
      queryClient.setQueryData(["project", id], updated);
      toast.info("Analyzing the transcript — the AI is planning your scenes");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const clearScenes = useMutation({
    mutationFn: () => apiDelete<{ ok: boolean }>(`/projects/${id}/scenes`),
    onSuccess: () => {
      toast.success("Scene plan cleared");
      void queryClient.invalidateQueries({ queryKey: ["project", id] });
      void queryClient.invalidateQueries({ queryKey: ["scenes", id] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const playScene = useCallback(
    (scene: Scene) => {
      engine.seek(scene.start_time + 0.01);
      engine.play();
      setInspectedSceneId(null);
    },
    [engine],
  );

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
    const notFound =
      projectQuery.error instanceof Error &&
      "status" in projectQuery.error &&
      (projectQuery.error as { status: number }).status === 404;
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
  const planning = project.scene_planning;
  const planningBusy = planning.status === "queued" || planning.status === "processing";
  const transcriptReady = project.transcription.status === "ready";
  const plannerConfigured = system?.scene_planning.configured !== false;
  const canPlan = transcriptReady && plannerConfigured && !planningBusy;

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
                {planning.status !== "idle" ? (
                  <span
                    className={badgeVariants({
                      variant: "outline",
                      className: `font-mono text-[10px] uppercase tracking-wider ${
                        planning.status === "ready"
                          ? "border-emerald-500/40 text-emerald-300"
                          : planning.status === "failed"
                            ? "border-red-500/40 text-red-300"
                            : "border-amber-500/40 text-amber-300"
                      }`,
                    })}
                    data-testid="scene-planning-status-badge"
                  >
                    {planning.status === "ready"
                      ? `${planning.scene_count} scenes planned`
                      : planning.status === "failed"
                        ? "scene planning failed"
                        : "planning scenes…"}
                  </span>
                ) : null}
                <span className="font-mono text-[10px] tracking-wider text-muted-foreground" data-testid="project-file-meta">
                  {project.audio.file_name} · {formatBytes(project.audio.size_bytes)}
                  {project.transcription.model ? ` · ${project.transcription.model}` : ""}
                  {planning.model ? ` · ${planning.model}` : ""}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              data-testid="analyze-create-scenes-button"
              onClick={() => planScenes.mutate()}
              disabled={!canPlan || planScenes.isPending}
              title={
                !plannerConfigured
                  ? "The AI planner is not configured — add GEMINI_API_KEY to backend/.env"
                  : !transcriptReady
                    ? "Waiting for the transcript"
                    : "Plan visual scenes from the transcript"
              }
              className="gap-2"
            >
              {planningBusy || planScenes.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              {planningBusy
                ? "Analyzing…"
                : scenes.length > 0
                  ? "Re-analyze Scenes"
                  : "Analyze & Create Scenes"}
            </Button>
            <Button
              variant="outline"
              data-testid="render-video-button"
              onClick={() => setRenderOpen(true)}
              className="gap-2"
            >
              <Clapperboard className="size-4" />
              Render video
            </Button>
          </div>
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

        {planning.status === "failed" ? (
          <div
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-300"
            data-testid="scene-planning-error-banner"
          >
            <span className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" />
              Scene planning failed — {planning.error ?? "the AI request did not succeed"}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => planScenes.mutate()}
              disabled={planScenes.isPending || !canPlan}
              data-testid="scene-planning-retry-button"
              className="border-red-500/40 text-red-200"
            >
              Retry
            </Button>
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
              click the timeline to scrub · click a scene to inspect its visual plan
            </p>
          </CardContent>
        </Card>

        {/* timeline */}
        <Timeline
          duration={duration}
          currentTime={engine.currentTime}
          peaks={project.audio.waveform}
          segments={segments}
          scenes={scenes}
          transcriptState={project.transcription.status}
          scenePlanningState={planning.status}
          activeSceneId={inspectedSceneId ?? playingSceneId}
          onSeek={engine.seek}
          onSelectScene={(scene) => setInspectedSceneId(scene.id)}
        />

        {/* inspectors */}
        <div className="grid gap-4 lg:grid-cols-2">
          <TranscriptPanel
            state={project.transcription.status}
            segments={segments}
            activeIndex={activeIndex}
            loading={transcriptQuery.isPending || (transcriptQuery.isFetching && segments.length === 0)}
            onSeek={engine.seek}
            onRetry={() => retryTranscription.mutate()}
            retrying={retryTranscription.isPending}
            errorText={project.transcription.error}
          />
          <ScenesPanel
            scenes={scenes}
            planning={planning}
            activeSceneId={inspectedSceneId ?? playingSceneId}
            onSelect={(scene) => setInspectedSceneId(scene.id)}
            onPlan={() => planScenes.mutate()}
            onClear={() => clearScenes.mutate()}
            planPending={planScenes.isPending}
            clearPending={clearScenes.isPending}
            plannerConfigured={plannerConfigured}
            transcriptReady={transcriptReady}
          />
        </div>
      </main>

      <SceneInspector
        scene={inspectedScene}
        onOpenChange={(open) => {
          if (!open) setInspectedSceneId(null);
        }}
        onPlayScene={playScene}
      />
      <RenderDialog open={renderOpen} onOpenChange={setRenderOpen} />
    </div>
  );
}
