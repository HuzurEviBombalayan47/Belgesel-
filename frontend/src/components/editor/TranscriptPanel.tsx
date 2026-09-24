import { memo, useEffect, useRef } from "react";
import { Loader2, Mic, RefreshCw, TriangleAlert } from "lucide-react";
import { formatClock } from "@/lib/format";
import type { TranscriptSegment } from "@/lib/types";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TranscriptRow = memo(function TranscriptRow({
  segment,
  active,
  onSeek,
}: {
  segment: TranscriptSegment;
  active: boolean;
  onSeek: (t: number) => void;
}) {
  return (
    <button
      type="button"
      data-testid={`transcript-segment-${segment.index}`}
      onClick={() => onSeek(segment.start_seconds + 0.01)}
      className={`flex w-full gap-3 rounded-lg border px-3 py-2 text-left transition-colors duration-150 ${
        active ? "border-gold/70 bg-gold/5" : "border-transparent hover:border-border hover:bg-muted/40"
      }`}
    >
      <span className="mt-0.5 shrink-0 font-mono text-xs tabular-nums text-gold" data-testid="transcript-timestamp">
        {formatClock(segment.start_seconds)}
      </span>
      <span className="text-sm leading-relaxed text-foreground/90">{segment.text}</span>
    </button>
  );
});

interface TranscriptPanelProps {
  state: string;
  segments: TranscriptSegment[];
  activeIndex: number | null;
  onSeek: (t: number) => void;
  onRetry: () => void;
  retrying: boolean;
  errorText: string | null;
}

/** Transcript inspector — real Whisper segments with clickable timestamps. */
export default function TranscriptPanel({ state, segments, activeIndex, onSeek, onRetry, retrying, errorText }: TranscriptPanelProps) {
  const activeRow = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    activeRow.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIndex]);

  return (
    <Card data-testid="transcript-panel" className="flex h-full flex-col border-border/80 bg-card">
      <CardHeader className="flex-row items-center justify-between border-b border-border/60 py-3">
        <CardTitle className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          <Mic className="size-3.5 text-primary" />
          Transcript
        </CardTitle>
        {state === "ready" && segments.length > 0 ? (
          <Badge variant="outline" className="font-mono text-[10px] border-emerald-500/40 text-emerald-300" data-testid="transcript-count-badge">
            {segments.length} segments
          </Badge>
        ) : null}
        {state === "failed" ? (
          <Button
            variant="outline"
            size="xs"
            data-testid="transcript-retry-button"
            onClick={onRetry}
            disabled={retrying}
            className="gap-1.5 border-red-500/40 text-red-300"
          >
            {retrying ? <Loader2 className="size-3 animate-spin" /> : <RefreshCw className="size-3" />}
            Retry
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="max-h-[340px] flex-1 space-y-1 overflow-y-auto p-2">
        {state === "pending" || state === "processing" ? (
          <div className="flex h-40 flex-col items-center justify-center gap-3" data-testid="transcript-processing">
            <span className="flex items-end gap-1" aria-hidden>
              {[0, 1, 2, 3].map((bar) => (
                <span
                  key={bar}
                  className="w-1.5 origin-bottom animate-eq rounded-sm bg-gold"
                  style={{ height: 20, animationDelay: `${bar * 0.15}s` }}
                />
              ))}
            </span>
            <p className="font-mono text-xs tracking-wide text-muted-foreground">Transcribing speech…</p>
          </div>
        ) : state === "failed" ? (
          <div className="flex h-40 flex-col items-center justify-center gap-2 px-6 text-center" data-testid="transcript-failed">
            <TriangleAlert className="size-5 text-red-400" />
            <p className="text-sm text-red-300">{errorText ?? "Transcription failed."}</p>
            <p className="text-xs text-muted-foreground">The narration itself is safe — retry when ready.</p>
          </div>
        ) : state === "unavailable" ? (
          <div className="flex h-40 flex-col items-center justify-center gap-2 px-6 text-center" data-testid="transcript-unavailable">
            <Mic className="size-5 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Transcription is not configured — add{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs text-gold">EMERGENT_LLM_KEY</code> to backend/.env.
            </p>
          </div>
        ) : segments.length === 0 ? (
          <div className="flex h-40 items-center justify-center px-6 text-center" data-testid="transcript-empty">
            <p className="text-sm text-muted-foreground">No speech detected in this narration.</p>
          </div>
        ) : (
          <div className="space-y-1" data-testid="transcript-list">
            {segments.map((segment, index) =>
              index === activeIndex ? (
                <div key={segment.id} ref={activeRow}>
                  <TranscriptRow segment={segment} active onSeek={onSeek} />
                </div>
              ) : (
                <TranscriptRow key={segment.id} segment={segment} active={false} onSeek={onSeek} />
              ),
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
