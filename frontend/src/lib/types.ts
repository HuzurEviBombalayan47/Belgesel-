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
  scene_planning: ScenePlanningInfo;
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
  scene_planning_status: string;
  scene_count: number;
  created_at: string;
}

export type SceneType =
  | "PHOTO"
  | "VIDEO"
  | "HISTORICAL_IMAGE"
  | "DOCUMENT"
  | "MAP"
  | "CHART"
  | "TEXT_ANIMATION"
  | "MOTION_GRAPHIC"
  | "LOGO"
  | "SCREENSHOT"
  | "MIXED";

export type ScenePlanningState = "idle" | "queued" | "processing" | "ready" | "failed";

export interface ScenePlanningInfo {
  status: ScenePlanningState;
  error: string | null;
  scene_count: number;
  model: string | null;
  segments_planned: number;
  segments_total: number;
  completed_at: string | null;
}

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

/** One planned visual beat — the structured plan stage 3 will bind real assets to. */
export interface Scene {
  id: string;
  project_id: string;
  index: number;
  start_time: number;
  end_time: number;
  transcript_text: string;
  scene_type: SceneType;
  visual_goal: string;
  visual_search_queries: string[];
  suggested_visual_treatment: string;
  important_text: string[];
  animation_type: string;
  transition_type: string;
  sound_effect_suggestion: string | null;
  status: string;
  asset_ids: string[];
  created_at: string;
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
  scene_planning: { configured: boolean; model: string | null };
  rendering: { enabled: boolean; stage: number };
  max_upload_bytes: number;
}
