import { Clapperboard, Film, Map, Type } from "lucide-react";
import { formatClock } from "@/lib/format";
import type { Scene } from "@/lib/types";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TREATMENT_LABELS: Record<string, string> = {
  ken_burns: "Ken Burns photo",
  archival_photo: "Archival photo",
  map: "Map sequence",
  chart: "Chart graphic",
  motion_typography: "Kinetic type",
  stock_footage: "Stock footage",
  title_card: "Title card",
};

/** Stage-2 roadmap of documentary treatments the scene planner will produce. */
const ROADMAP = [
  {
    icon: Film,
    label: "Archival Photo Animation",
    desc: "Ken Burns 2.5D parallax, grain and sepia treatment on historical photographs",
  },
  {
    icon: Map,
    label: "Dynamic Historical Maps",
    desc: "Animated route lines, territory shading and camera pans across vintage cartography",
  },
  {
    icon: Type,
    label: "Documentary Kinetic Type",
    desc: "Keyword magnification and emphasis on the words and numbers that matter",
  },
  {
    icon: Clapperboard,
    label: "Cinematic B-Roll & Footage",
    desc: "Contextual stock footage, transitions and synchronized sound effects",
  },
];

interface ScenesPanelProps {
  scenes: Scene[];
}

/** Visual-scenes inspector: renders real scene rows when the planner writes them,
 * otherwise shows the honest stage-2 roadmap. */
export default function ScenesPanel({ scenes }: ScenesPanelProps) {
  return (
    <Card data-testid="scenes-panel" className="flex h-full flex-col border-border/80 bg-card">
      <CardHeader className="flex-row items-center justify-between border-b border-border/60 py-3">
        <CardTitle className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          <Clapperboard className="size-3.5 text-primary" />
          Visual scenes
        </CardTitle>
        <Badge variant="outline" className="font-mono text-[10px] border-amber-500/40 text-amber-300">
          stage 2
        </Badge>
      </CardHeader>
      <CardContent className="max-h-[340px] flex-1 space-y-2 overflow-y-auto p-3">
        {scenes.length > 0 ? (
          <ul className="space-y-2" data-testid="scene-list">
            {scenes.map((scene) => (
              <li
                key={scene.id}
                data-testid={`scene-row-${scene.index}`}
                className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-heading text-sm text-foreground">
                    {scene.title ?? TREATMENT_LABELS[scene.treatment ?? ""] ?? `Scene ${scene.index + 1}`}
                  </span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                    {formatClock(scene.start_seconds)}–{formatClock(scene.end_seconds)}
                  </span>
                </div>
                {scene.brief ? <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{scene.brief}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <div className="space-y-2" data-testid="scenes-roadmap">
            {ROADMAP.map((item) => (
              <div
                key={item.label}
                className="flex gap-3 rounded-lg border border-border/70 bg-timeline/60 px-3 py-2.5"
                data-testid="scenes-roadmap-item"
              >
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md border border-border bg-muted text-gold">
                  <item.icon className="size-3.5" />
                </span>
                <div>
                  <p className="text-sm font-medium text-foreground">{item.label}</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">{item.desc}</p>
                </div>
              </div>
            ))}
            <p className="px-1 pt-1 font-mono text-[10px] leading-relaxed tracking-wide text-muted-foreground">
              The AI scene planner reads the transcript and fills the timeline lane above in
              stage 2 — the data contract is already live.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
