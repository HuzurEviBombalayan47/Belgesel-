import type { TranscriptionStatus } from "@/lib/types";

/** Shared pill styling for transcription states — used on cards and in the editor. */
export function transcriptionBadge(status: string): { label: string; className: string } {
  switch (status) {
    case "ready":
      return { label: "transcript ready", className: "border-emerald-500/40 text-emerald-300" };
    case "processing":
      return { label: "transcribing…", className: "border-amber-500/40 text-amber-300" };
    case "pending":
      return { label: "transcript queued", className: "border-amber-500/40 text-amber-300" };
    case "failed":
      return { label: "transcript failed", className: "border-red-500/40 text-red-300" };
    default:
      return { label: "no transcription", className: "border-border text-muted-foreground" };
  }
}
