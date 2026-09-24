import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Loader2, ZoomIn, ZoomOut } from "lucide-react";
import { formatClock } from "@/lib/format";
import { sceneStyle } from "@/lib/sceneStyles";
import type { Scene, TranscriptSegment } from "@/lib/types";
import { Button } from "@/components/ui/button";

const LANE_LABEL_W = 96;
const RULER_H = 28;
const TICK_STEPS = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];

interface TimelineProps {
  duration: number;
  currentTime: number;
  peaks: number[] | null;
  segments: TranscriptSegment[];
  scenes: Scene[];
  transcriptState: string;
  scenePlanningState: string;
  activeSceneId: string | null;
  onSeek: (t: number) => void;
  onSelectScene: (scene: Scene) => void;
}

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

function EmptyLane({ text, testid }: { text: string; testid: string }) {
  return (
    <div
      data-testid={testid}
      className="absolute inset-x-2 top-2 bottom-2 flex items-center justify-center rounded-md border border-dashed border-border/80 bg-transparent px-4"
    >
      <span className="truncate font-mono text-[11px] tracking-wide text-muted-foreground">{text}</span>
    </div>
  );
}

const TranscriptBlock = memo(function TranscriptBlock({
  segment,
  pps,
  active,
  onSeek,
}: {
  segment: TranscriptSegment;
  pps: number;
  active: boolean;
  onSeek: (t: number) => void;
}) {
  return (
    <button
      type="button"
      data-testid={`transcript-segment-${segment.index}`}
      onClick={(event) => {
        event.stopPropagation();
        onSeek(segment.start_seconds + 0.01);
      }}
      title={segment.text}
      className={`absolute top-2 bottom-2 overflow-hidden rounded-md border px-2 py-1 text-left transition-colors duration-150 ${
        active
          ? "animate-pulse-soft border-gold bg-gold/10"
          : "border-[#1E3A5F] bg-[#132338] hover:border-gold/50"
      }`}
      style={{ left: segment.start_seconds * pps, width: Math.max(2, (segment.end_seconds - segment.start_seconds) * pps) }}
    >
      <span className="pointer-events-none block truncate text-[11px] leading-4 text-sky-100">{segment.text}</span>
    </button>
  );
});

const SceneBlock = memo(function SceneBlock({
  scene,
  pps,
  active,
  onSelect,
}: {
  scene: Scene;
  pps: number;
  active: boolean;
  onSelect: (scene: Scene) => void;
}) {
  const style = sceneStyle(scene.scene_type);
  const width = Math.max(3, (scene.end_time - scene.start_time) * pps);
  return (
    <button
      type="button"
      data-testid={`scene-block-${scene.index}`}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(scene);
      }}
      onPointerDown={(event) => event.stopPropagation()}
      title={`${style.label} · ${scene.visual_goal}`}
      className={`absolute top-2 bottom-2 overflow-hidden rounded-md border px-1.5 py-1 text-left transition-colors duration-150 ${style.block} ${
        active ? "ring-2 ring-gold ring-offset-1 ring-offset-timeline" : ""
      }`}
      style={{ left: scene.start_time * pps, width }}
    >
      <span className="pointer-events-none block font-mono text-[9px] uppercase leading-3 tracking-wider opacity-80">
        {style.short}
      </span>
      {width > 60 ? (
        <span className="pointer-events-none mt-0.5 block truncate text-[10px] leading-3 text-foreground/90">
          {scene.visual_goal}
        </span>
      ) : null}
      {width > 110 && scene.important_text.length > 0 ? (
        <span className="pointer-events-none mt-0.5 block truncate font-heading text-[10px] font-semibold text-gold">
          {scene.important_text.slice(0, 2).join(" · ")}
        </span>
      ) : null}
    </button>
  );
});

/** Multi-lane NLE timeline: ruler + playhead, scenes lane, transcript lane, waveform.
 * Click or drag anywhere to scrub; the playhead follows the audio engine via rAF. */
export default function Timeline({
  duration,
  currentTime,
  peaks,
  segments,
  scenes,
  transcriptState,
  scenePlanningState,
  activeSceneId,
  onSeek,
  onSelectScene,
}: TimelineProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const rulerRef = useRef<HTMLCanvasElement | null>(null);
  const waveRef = useRef<HTMLCanvasElement | null>(null);
  const [width, setWidth] = useState(0);
  const [pps, setPps] = useState(0);
  const userZoomed = useRef(false);
  const dragging = useRef(false);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    observer.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);

  const fitPps = duration > 0 && width > 0 ? (width - LANE_LABEL_W - 12) / duration : 0;

  useEffect(() => {
    if (!userZoomed.current && fitPps > 0) setPps(fitPps);
  }, [fitPps]);

  const zoom = (factor: number) => {
    if (fitPps <= 0) return;
    userZoomed.current = true;
    setPps((current) => clamp(current * factor || fitPps, Math.max(0.05, fitPps * 0.5), 800));
  };
  const fit = () => {
    userZoomed.current = false;
    if (fitPps > 0) setPps(fitPps);
  };

  const contentW = Math.max(width - LANE_LABEL_W - 12, duration * pps);

  // ---- ruler -------------------------------------------------------------
  useEffect(() => {
    const canvas = rulerRef.current;
    if (!canvas || contentW <= 0 || pps <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(contentW * dpr);
    canvas.height = Math.floor(RULER_H * dpr);
    canvas.style.width = `${contentW}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, contentW, RULER_H);

    const step = TICK_STEPS.find((candidate) => candidate * pps >= 80) ?? 3600;
    const sub = step / 5;
    ctx.strokeStyle = "#334155";
    ctx.fillStyle = "#64748B";
    ctx.font = "10px 'JetBrains Mono Variable', monospace";
    for (let t = 0; t <= duration + step; t += sub) {
      const x = Math.round(t * pps) + 0.5;
      if (x > contentW) break;
      const major = Math.abs(t / step - Math.round(t / step)) < 1e-9;
      ctx.globalAlpha = major ? 1 : 0.45;
      ctx.beginPath();
      ctx.moveTo(x, major ? 9 : 18);
      ctx.lineTo(x, RULER_H);
      ctx.stroke();
      if (major) ctx.fillText(formatClock(t), x + 4, 11);
    }
  }, [pps, contentW, duration]);

  // ---- waveform ------------------------------------------------------------
  useEffect(() => {
    const canvas = waveRef.current;
    if (!canvas || contentW <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    const height = canvas.parentElement?.clientHeight ?? 64;
    canvas.width = Math.floor(contentW * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${contentW}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, contentW, height);

    if (!peaks || peaks.length === 0) {
      ctx.fillStyle = "#38BDF8";
      ctx.globalAlpha = 0.35;
      ctx.fillRect(0, height / 2, contentW, 1);
      return;
    }
    ctx.fillStyle = "#38BDF8";
    const barW = 2;
    for (let x = 0; x < contentW; x += barW + 1) {
      const sample = peaks[Math.min(peaks.length - 1, Math.floor((x / contentW) * peaks.length))] ?? 0;
      const barH = Math.max(2, sample * (height - 10));
      ctx.globalAlpha = 0.35 + sample * 0.65;
      ctx.fillRect(x, (height - barH) / 2, barW, barH);
    }
  }, [peaks, contentW]);

  // keep the playhead in view while playing
  useEffect(() => {
    const scroll = scrollRef.current;
    if (!scroll || dragging.current || duration <= 0 || pps <= 0) return;
    const px = currentTime * pps;
    const view = scroll.clientWidth;
    if (px < scroll.scrollLeft + 40 || px > scroll.scrollLeft + view - 40) {
      scroll.scrollLeft = Math.max(0, px - view / 2);
    }
  }, [currentTime, pps, duration]);

  const seekFromClientX = (clientX: number) => {
    const el = contentRef.current;
    if (!el || pps <= 0 || duration <= 0) return;
    const rect = el.getBoundingClientRect();
    onSeek(clamp((clientX - rect.left) / pps, 0, duration));
  };

  const transcriptBlocks = useMemo(
    () =>
      segments.map((segment) => (
        <TranscriptBlock
          key={segment.id}
          segment={segment}
          pps={pps}
          active={false}
          onSeek={onSeek}
        />
      )),
    [segments, pps, onSeek],
  );
  const sceneBlocks = useMemo(
    () =>
      scenes.map((scene) => (
        <SceneBlock
          key={scene.id}
          scene={scene}
          pps={pps}
          active={scene.id === activeSceneId}
          onSelect={onSelectScene}
        />
      )),
    [scenes, pps, activeSceneId, onSelectScene],
  );

  const scenesLane = () => {
    if (scenes.length > 0) return <>{sceneBlocks}</>;
    if (scenePlanningState === "queued" || scenePlanningState === "processing") {
      return (
        <div
          className="absolute inset-x-2 top-2 bottom-2 flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3"
          data-testid="scenes-lane-planning"
        >
          <Loader2 className="size-3.5 animate-spin text-amber-300" />
          <span className="font-mono text-[11px] tracking-wide text-amber-200">
            AI is planning your visual scenes…
          </span>
        </div>
      );
    }
    if (scenePlanningState === "failed") {
      return <EmptyLane testid="scenes-lane-failed" text="Scene planning failed — see the scenes panel" />;
    }
    return (
      <EmptyLane
        testid="scenes-lane-empty"
        text="Run “Analyze & Create Scenes” to fill this lane with the AI's visual plan"
      />
    );
  };

  const transcriptLane = () => {
    if (transcriptState === "pending" || transcriptState === "processing") {
      return (
        <div className="absolute inset-x-2 top-2 bottom-2 flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3">
          <Loader2 className="size-3.5 animate-spin text-amber-300" />
          <span className="font-mono text-[11px] tracking-wide text-amber-200">
            Transcribing speech with Whisper…
          </span>
        </div>
      );
    }
    if (transcriptState === "failed") {
      return <EmptyLane testid="transcript-lane-failed" text="Transcription failed — retry from the transcript panel" />;
    }
    if (transcriptState === "unavailable") {
      return <EmptyLane testid="transcript-lane-unavailable" text="Transcription not configured — set EMERGENT_LLM_KEY" />;
    }
    if (segments.length === 0) {
      return <EmptyLane testid="transcript-lane-empty" text="Transcript segments appear here after speech analysis" />;
    }
    return <>{transcriptBlocks}</>;
  };

  return (
    <div
      ref={wrapRef}
      data-testid="timeline"
      className="film-grain relative overflow-hidden rounded-xl border border-border bg-timeline"
    >
      <div className="flex items-center justify-between border-b border-border/70 px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Timeline
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label="Zoom out"
            data-testid="timeline-zoom-out"
            onClick={() => zoom(1 / 1.5)}
          >
            <ZoomOut className="size-3.5" />
          </Button>
          <Button variant="ghost" size="xs" data-testid="timeline-zoom-fit" onClick={fit} className="font-mono text-[11px]">
            Fit
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label="Zoom in"
            data-testid="timeline-zoom-in"
            onClick={() => zoom(1.5)}
          >
            <ZoomIn className="size-3.5" />
          </Button>
        </div>
      </div>

      <div ref={scrollRef} className="overflow-x-auto">
        <div
          ref={contentRef}
          data-testid="timeline-body"
          className="relative select-none"
          style={{ width: LANE_LABEL_W + contentW, touchAction: "pan-x" }}
          onPointerDown={(event) => {
            dragging.current = true;
            (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
            seekFromClientX(event.clientX);
          }}
          onPointerMove={(event) => {
            if (dragging.current) seekFromClientX(event.clientX);
          }}
          onPointerUp={() => {
            dragging.current = false;
          }}
          onPointerCancel={() => {
            dragging.current = false;
          }}
        >
          {/* ruler */}
          <div className="flex">
            <div
              className="sticky left-0 z-20 flex shrink-0 items-end justify-end bg-timeline px-2 pb-1 font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground"
              style={{ width: LANE_LABEL_W }}
            >
              time
            </div>
            <canvas ref={rulerRef} data-testid="timeline-ruler" style={{ height: RULER_H, width: contentW }} />
          </div>

          {/* scenes lane */}
          <div className="flex border-t border-border/60">
            <div
              className="sticky left-0 z-20 flex shrink-0 items-center justify-end bg-timeline px-2 font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground"
              style={{ width: LANE_LABEL_W }}
            >
              scenes
            </div>
            <div className="relative h-16 flex-1" data-testid="timeline-lane-scenes" style={{ width: contentW }}>
              {scenesLane()}
            </div>
          </div>

          {/* transcript lane */}
          <div className="flex border-t border-border/60">
            <div
              className="sticky left-0 z-20 flex shrink-0 items-center justify-end bg-timeline px-2 font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground"
              style={{ width: LANE_LABEL_W }}
            >
              transcript
            </div>
            <div className="relative h-16 flex-1" data-testid="timeline-lane-transcript" style={{ width: contentW }}>
              {transcriptLane()}
            </div>
          </div>

          {/* audio lane */}
          <div className="flex border-t border-border/60">
            <div
              className="sticky left-0 z-20 flex shrink-0 items-center justify-end bg-timeline px-2 font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground"
              style={{ width: LANE_LABEL_W }}
            >
              audio
            </div>
            <div
              className="relative h-20 flex-1 bg-[#071829]"
              data-testid="timeline-lane-audio"
              style={{ width: contentW }}
            >
              {peaks ? null : (
                <span className="absolute right-3 top-2 font-mono text-[10px] text-muted-foreground">
                  waveform unavailable
                </span>
              )}
              <canvas ref={waveRef} data-testid="timeline-waveform" />
            </div>
          </div>

          {/* playhead */}
          <div
            data-testid="timeline-playhead"
            className="pointer-events-none absolute top-0 bottom-0 z-10 w-px bg-[#EF4444]"
            style={{
              left: LANE_LABEL_W + (duration > 0 && pps > 0 ? clamp(currentTime, 0, duration) * pps : 0),
              boxShadow: "0 0 8px rgba(239,68,68,0.6)",
            }}
          >
            <div className="absolute -left-[5px] top-0 size-2.5 rounded-sm bg-[#EF4444]" />
          </div>
        </div>
      </div>
    </div>
  );
}
