// Hand-written mirrors of the backend Pydantic models (backend/models/*).
// Nothing infers across the Python/TypeScript boundary — keep these in sync
// with the models in the same edit.

export type ProjectStatus = "ready" | "failed";

export type TranscriptionStatus = "pending" | "processing" | "ready" | "failed" | "unavailable";

export interface AudioAsset {
  object_key: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  duration_seconds: number | null;
  /** Normalized 0..1 peak envelope of the real audio, oldest sample first. */
  waveform: number[] | null;
}

export interface TranscriptionInfo {
  status: TranscriptionStatus;
  error: string | null;
  segment_count: number;
  language: string | null;
  model: string | null;
  completed_at: string | null;
}

export interface Project {
  id: string;
  title: string;
  status: ProjectStatus;
  audio: AudioAsset;
  transcription: TranscriptionInfo;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  title: string;
  status: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  duration_seconds: number | null;
  transcription_status: string;
  segment_count: number;
  created_at: string;
}

export type SceneTreatment =
  | "ken_burns"
  | "map"
  | "chart"
  | "motion_typography"
  | "stock_footage"
  | "archival_photo"
  | "title_card";

export interface TranscriptSegment {
  id: string;
  project_id: string;
  index: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
  speaker: string | null;
  confidence: number | null;
}

export interface Scene {
  id: string;
  project_id: string;
  index: number;
  start_seconds: number;
  end_seconds: number;
  title: string | null;
  treatment: SceneTreatment | null;
  brief: string | null;
  status: "planned" | "awaiting_assets" | "ready";
  asset_ids: string[];
}

export interface RenderOutput {
  object_key: string;
  size_bytes: number;
  duration_seconds: number | null;
}

export interface RenderJob {
  id: string;
  project_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  output: RenderOutput | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface SystemStatus {
  app: string;
  version: string;
  storage: { provider: string; configured: boolean; bucket: string | null };
  transcription: { configured: boolean; model: string | null };
  scene_planning: { enabled: boolean; stage: number };
  rendering: { enabled: boolean; stage: number };
  max_upload_bytes: number;
}
