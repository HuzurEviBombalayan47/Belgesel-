import { Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { formatSMPTE } from "@/lib/format";
import { Button } from "@/components/ui/button";

interface AudioTransportProps {
  playing: boolean;
  currentTime: number;
  duration: number | null;
  onToggle: () => void;
  onSkip: (delta: number) => void;
}

/** Broadcast-style transport: ±5s shuttle, amber play button, SMPTE timecode. */
export default function AudioTransport({ playing, currentTime, duration, onToggle, onSkip }: AudioTransportProps) {
  return (
    <div className="flex items-center gap-3 sm:gap-4">
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Skip back 5 seconds"
        data-testid="transport-skip-back-button"
        onClick={() => onSkip(-5)}
      >
        <SkipBack className="size-4" />
      </Button>
      <Button
        size="icon"
        aria-label={playing ? "Pause" : "Play"}
        data-testid="transport-play-button"
        onClick={onToggle}
        className="rounded-full bg-primary text-primary-foreground shadow-[0_0_24px_rgba(245,158,11,0.35)] hover:bg-primary/90"
      >
        {playing ? <Pause className="size-5" /> : <Play className="size-5 translate-x-[1px]" />}
      </Button>
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Skip forward 5 seconds"
        data-testid="transport-skip-forward-button"
        onClick={() => onSkip(5)}
      >
        <SkipForward className="size-4" />
      </Button>

      <div
        data-testid="timecode-readout"
        className="ml-1 font-mono text-sm tabular-nums tracking-wider"
        title="SMPTE @ 30 fps"
      >
        <span className="text-gold drop-shadow-[0_0_6px_rgba(251,191,36,0.35)]">{formatSMPTE(currentTime)}</span>
        <span className="text-muted-foreground"> / {formatSMPTE(duration ?? 0)}</span>
      </div>
    </div>
  );
}
