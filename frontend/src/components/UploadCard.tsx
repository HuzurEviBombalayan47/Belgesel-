import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Mic, TriangleAlert, UploadCloud } from "lucide-react";
import { apiUpload } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatBytes } from "@/lib/format";
import type { Project, SystemStatus } from "@/lib/types";
import { useSystemStatus, StorageSetupDialog } from "@/components/StorageBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const ALLOWED_EXTENSIONS = [".mp3", ".wav", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".flac", ".webm"];

type Phase = "idle" | "analyzing" | "uploading" | "done" | "error";

/** Decode the real audio in the browser and reduce it to a normalized peak envelope
 * (2000 buckets). This is measured from the actual samples — not simulated. */
async function computePeaks(file: File): Promise<{ peaks: number[]; duration: number } | null> {
  try {
    if (file.size > 120 * 1024 * 1024) return null; // decoding huge files in-browser is wasteful
    const buffer = await file.arrayBuffer();
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    const ctx = new Ctor();
    try {
      const audio = await ctx.decodeAudioData(buffer);
      const channel = audio.getChannelData(0);
      const buckets = 2000;
      const block = Math.max(1, Math.floor(channel.length / buckets));
      const peaks: number[] = [];
      let max = 0.0001;
      for (let i = 0; i < buckets; i++) {
        let peak = 0;
        const start = i * block;
        for (let j = 0; j < block; j += 16) {
          const sample = Math.abs(channel[start + j] ?? 0);
          if (sample > peak) peak = sample;
        }
        peaks.push(peak);
        if (peak > max) max = peak;
      }
      return {
        peaks: peaks.map((p) => Math.round((p / max) * 1000) / 1000),
        duration: audio.duration,
      };
    } finally {
      void ctx.close();
    }
  } catch {
    return null; // waveform is optional; the server still probes duration
  }
}

export default function UploadCard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { data: status } = useSystemStatus();

  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [fileMeta, setFileMeta] = useState<{ name: string; size: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const maxBytes = status?.max_upload_bytes ?? 250 * 1024 * 1024;
  const storageReady = status?.storage.configured === true;
  const busy = phase === "analyzing" || phase === "uploading";

  async function pick(file: File | undefined) {
    if (!file || busy) return;
    setError(null);

    const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`“${file.name}” is not a supported audio file — use ${ALLOWED_EXTENSIONS.join(", ")}`);
      setPhase("idle");
      return;
    }
    if (file.size > maxBytes) {
      setError(`That file is ${formatBytes(file.size)} — the limit is ${formatBytes(maxBytes)}.`);
      setPhase("idle");
      return;
    }

    setFileMeta({ name: file.name, size: file.size });

    try {
      setPhase("analyzing");
      const decoded = await computePeaks(file);

      setPhase("uploading");
      setProgress(0);
      const form = new FormData();
      form.append("file", file);
      if (decoded) {
        form.append("peaks", JSON.stringify(decoded.peaks));
        form.append("client_duration", String(decoded.duration));
      }
      const project = await apiUpload<Project>("/projects", form, setProgress);
      setPhase("done");
      toast.success("Project created — transcribing in the background");
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setPhase("error");
      setError(errorMessage(err));
    }
  }

  if (!storageReady && status) {
    // Honest setup state — no pretend uploads.
    return (
      <Card data-testid="upload-storage-missing">
        <CardContent className="flex flex-col items-start gap-4 p-8">
          <span className="flex size-10 items-center justify-center rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-300">
            <TriangleAlert className="size-5" />
          </span>
          <div className="space-y-1">
            <h3 className="font-heading text-lg font-semibold text-foreground">Object storage not connected</h3>
            <p className="max-w-md text-sm text-muted-foreground">
              Chronicle uploads straight into your Cloudflare R2 bucket. Add the{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs text-gold">R2_*</code> keys to{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs text-gold">backend/.env</code> and
              restart the backend to enable uploads.
            </p>
          </div>
          <StorageSetupDialog>
            <Button variant="outline" size="sm" data-testid="storage-setup-open-button">
              Setup instructions
            </Button>
          </StorageSetupDialog>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/80 bg-card">
      <CardContent className="p-4 sm:p-6">
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(",") + ",audio/*"}
          className="hidden"
          data-testid="upload-file-input"
          onChange={(event) => {
            void pick(event.target.files?.[0]);
            event.target.value = "";
          }}
        />

        {phase === "uploading" ? (
          <div className="space-y-3 py-4" data-testid="upload-progress">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2 text-foreground">
                <Loader2 className="size-4 animate-spin text-primary" />
                Uploading {fileMeta?.name}
              </span>
              <span className="font-mono text-xs text-gold" data-testid="upload-progress-label">
                {progress}%
              </span>
            </div>
            <div
              className="h-2 w-full overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={progress}
              data-testid="upload-progress-bar"
            >
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-200 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Streaming into your R2 bucket, then probing duration and starting Whisper.
            </p>
          </div>
        ) : phase === "analyzing" ? (
          <div className="flex items-center gap-3 py-6" data-testid="upload-analyzing">
            <Loader2 className="size-5 animate-spin text-primary" />
            <div>
              <p className="text-sm text-foreground">Reading {fileMeta?.name}</p>
              <p className="text-xs text-muted-foreground">Decoding samples for the waveform…</p>
            </div>
          </div>
        ) : (
          <div
            data-testid="upload-audio-dropzone"
            role="button"
            tabIndex={0}
            aria-disabled={busy}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              void pick(event.dataTransfer.files?.[0]);
            }}
            className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors duration-200 ${
              dragging
                ? "border-primary bg-primary/5"
                : "border-border hover:border-gold/50 hover:bg-muted/40"
            }`}
          >
            <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <UploadCloud className="size-6" />
            </span>
            <div className="space-y-1">
              <p className="font-heading text-base font-semibold text-foreground">
                Drop your narration here
              </p>
              <p className="text-sm text-muted-foreground">
                or <span className="text-gold underline underline-offset-2">browse files</span> — one audio
                track per documentary
              </p>
            </div>
            <p className="font-mono text-[11px] tracking-wider text-muted-foreground">
              MP3 · WAV · M4A · AAC · OGG · OPUS · FLAC · WEBM — up to {formatBytes(maxBytes)}
            </p>
          </div>
        )}

        {error ? (
          <div
            data-testid="upload-error"
            className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            <div className="flex-1">
              {error}
              <Button
                variant="ghost"
                size="sm"
                className="ml-2 h-auto p-0 text-red-300 underline underline-offset-2"
                onClick={() => {
                  setError(null);
                  setPhase("idle");
                  setFileMeta(null);
                }}
              >
                Try again
              </Button>
            </div>
          </div>
        ) : null}

        <p className="mt-4 flex items-center gap-2 text-xs text-muted-foreground" data-testid="upload-pipeline-note">
          <Mic className="size-3.5 text-primary" />
          On upload: stored in R2 → duration probed → waveform built → Whisper transcribes with timestamps.
        </p>
      </CardContent>
    </Card>
  );
}
