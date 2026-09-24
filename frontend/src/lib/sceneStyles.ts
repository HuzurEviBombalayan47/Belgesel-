import type { SceneType } from "@/lib/types";

/** Per-scene-type identity: label, lane/badge colours and icon name.
 * One source of truth shared by the timeline lane, the scene list and the inspector. */
export interface SceneTypeStyle {
  label: string;
  short: string;
  /** timeline block classes */
  block: string;
  /** badge / chip classes */
  badge: string;
  /** hex used for canvas-free coloured accents */
  accent: string;
}

export const SCENE_TYPE_STYLES: Record<SceneType, SceneTypeStyle> = {
  PHOTO: {
    label: "Photo",
    short: "PHOTO",
    block: "border-sky-400/50 bg-sky-500/15 hover:border-sky-300",
    badge: "border-sky-400/50 text-sky-200",
    accent: "#38BDF8",
  },
  VIDEO: {
    label: "Video",
    short: "VIDEO",
    block: "border-violet-400/50 bg-violet-500/15 hover:border-violet-300",
    badge: "border-violet-400/50 text-violet-200",
    accent: "#A78BFA",
  },
  HISTORICAL_IMAGE: {
    label: "Historical image",
    short: "ARCHIVAL",
    block: "border-amber-400/60 bg-amber-500/15 hover:border-amber-300",
    badge: "border-amber-400/60 text-amber-200",
    accent: "#FBBF24",
  },
  DOCUMENT: {
    label: "Document",
    short: "DOC",
    block: "border-stone-300/40 bg-stone-300/10 hover:border-stone-200",
    badge: "border-stone-300/40 text-stone-200",
    accent: "#D6D3D1",
  },
  MAP: {
    label: "Map",
    short: "MAP",
    block: "border-emerald-400/50 bg-emerald-500/15 hover:border-emerald-300",
    badge: "border-emerald-400/50 text-emerald-200",
    accent: "#34D399",
  },
  CHART: {
    label: "Chart",
    short: "CHART",
    block: "border-teal-400/50 bg-teal-500/15 hover:border-teal-300",
    badge: "border-teal-400/50 text-teal-200",
    accent: "#2DD4BF",
  },
  TEXT_ANIMATION: {
    label: "Text animation",
    short: "TYPE",
    block: "border-rose-400/50 bg-rose-500/15 hover:border-rose-300",
    badge: "border-rose-400/50 text-rose-200",
    accent: "#FB7185",
  },
  MOTION_GRAPHIC: {
    label: "Motion graphic",
    short: "MOGRAPH",
    block: "border-fuchsia-400/50 bg-fuchsia-500/15 hover:border-fuchsia-300",
    badge: "border-fuchsia-400/50 text-fuchsia-200",
    accent: "#E879F9",
  },
  LOGO: {
    label: "Logo",
    short: "LOGO",
    block: "border-orange-400/50 bg-orange-500/15 hover:border-orange-300",
    badge: "border-orange-400/50 text-orange-200",
    accent: "#FB923C",
  },
  SCREENSHOT: {
    label: "Screenshot",
    short: "SCREEN",
    block: "border-cyan-400/50 bg-cyan-500/15 hover:border-cyan-300",
    badge: "border-cyan-400/50 text-cyan-200",
    accent: "#22D3EE",
  },
  MIXED: {
    label: "Mixed",
    short: "MIXED",
    block: "border-slate-300/40 bg-slate-300/10 hover:border-slate-200",
    badge: "border-slate-300/40 text-slate-200",
    accent: "#CBD5E1",
  },
};

export function sceneStyle(type: SceneType | string): SceneTypeStyle {
  return SCENE_TYPE_STYLES[type as SceneType] ?? SCENE_TYPE_STYLES.MIXED;
}

/** "KEN_BURNS_ZOOM_IN" -> "Ken burns zoom in" */
export function humanizeToken(token: string): string {
  const text = (token || "").replace(/_/g, " ").toLowerCase().trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "—";
}
