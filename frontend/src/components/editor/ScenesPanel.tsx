import { useMemo } from "react";
import {
  Clapperboard,
  Loader2,
  Search,
  Sparkles,
  TriangleAlert,
  Type,
  Volume2,
} from "lucide-react";
import { formatClock } from "@/lib/format";
import { sceneStyle } from "@/lib/sceneStyles";
import type { Scene, ScenePlanningInfo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ScenesPanelProps {
  scenes: Scene[];
  planning: ScenePlanningInfo;
  activeSceneId: string | null;
  onSelect: (scene: Scene) => void;
  onPlan: () => void;
  onClear: () => void;
  planPending: boolean;
  clearPending: boolean;
  plannerConfigured: boolean;
  transcriptReady: boolean;
}

/** Visual-scenes inspector: the AI's plan, one row per scene. Empty until the
 * planner runs — no placeholder scenes are ever shown. */
export default function ScenesPanel({
  scenes,
  planning,
  activeSceneId,
  onSelect,
  onPlan,
  onClear,
  planPending,
  clearPending,
  plannerConfigured,
  transcriptReady,
}: ScenesPanelProps) {
  const typeBreakdown = useMemo(() => {
    const counts = new Map<string, number>();
    for (const scene of scenes) counts.set(scene.scene_type, (counts.get(scene.scene_type) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [scenes]);

  const busy = planning.status === "queued" || planning.status === "processing";

  return (
    <Card data-testid="scenes-panel" className="flex h-full flex-col border-border/80 bg-card">
      <CardHeader className="flex-row items-center justify-between border-b border-border/60 py-3">
        <CardTitle className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          <Clapperboard className="size-3.5 text-primary" />
          Visual scenes
        </CardTitle>
        {scenes.length > 0 ? (
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className="border-emerald-500/40 font-mono text-[10px] text-emerald-300"
              data-testid="scene-count-badge"
            >
              {scenes.length} scenes
            </Badge>
            <Button
              variant="ghost"
              size="xs"
              data-testid="scenes-clear-button"
              onClick={onClear}
              disabled={clearPending || busy}
              className="font-mono text-[10px] text-muted-foreground"
            >
              {clearPending ? <Loader2 className="size-3 animate-spin" /> : null}
              Clear
            </Button>
          </div>
        ) : null}
      </CardHeader>

      <CardContent className="max-h-[420px] flex-1 space-y-2 overflow-y-auto p-3">
        {busy ? (
          <div className="flex h-44 flex-col items-center justify-center gap-3 text-center" data-testid="scenes-planning">
            <Loader2 className="size-5 animate-spin text-primary" />
            <div>
              <p className="text-sm text-foreground">
                {planning.status === "queued" ? "Queued for analysis…" : "Directing your documentary…"}
              </p>
              <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                {planning.model ?? "AI"} is planning visuals for {planning.segments_total} transcript
                segments
              </p>
            </div>
          </div>
        ) : planning.status === "failed" ? (
          <div className="flex min-h-44 flex-col items-center justify-center gap-2 px-4 text-center" data-testid="scenes-failed">
            <TriangleAlert className="size-5 text-red-400" />
            <p className="text-sm font-medium text-red-300">Scene planning failed</p>
            <p className="text-xs leading-relaxed text-muted-foreground" data-testid="scenes-error-text">
              {planning.error ?? "The AI request failed."}
            </p>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              no scenes were created
            </p>
            <Button variant="outline" size="sm" onClick={onPlan} disabled={planPending} data-testid="scenes-retry-button" className="mt-2">
              {planPending ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
              Try again
            </Button>
          </div>
        ) : scenes.length === 0 ? (
          <div className="flex min-h-44 flex-col items-center justify-center gap-2 px-5 text-center" data-testid="scenes-empty">
            <Sparkles className="size-5 text-gold" />
            <p className="font-heading text-sm text-foreground">No scene plan yet</p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {plannerConfigured
                ? transcriptReady
                  ? "Run “Analyze & Create Scenes” — the AI reads your transcript and decides what the viewer should see, beat by beat."
                  : "Waiting for the transcript — scenes are planned from timestamped speech."
                : "The AI planner is not configured — add GEMINI_API_KEY or EMERGENT_LLM_KEY to backend/.env."}
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5 pb-1" data-testid="scene-type-breakdown">
              {typeBreakdown.map(([type, count]) => (
                <span
                  key={type}
                  className={`rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${sceneStyle(type).badge}`}
                >
                  {sceneStyle(type).short} {count}
                </span>
              ))}
            </div>
            <ul className="space-y-2" data-testid="scene-list">
              {scenes.map((scene) => {
                const style = sceneStyle(scene.scene_type);
                const active = scene.id === activeSceneId;
                return (
                  <li key={scene.id}>
                    <button
                      type="button"
                      data-testid={`scene-row-${scene.index}`}
                      onClick={() => onSelect(scene)}
                      className={`w-full rounded-lg border px-3 py-2.5 text-left transition-colors duration-150 ${
                        active ? "border-gold/70 bg-gold/5" : "border-border/70 bg-timeline/60 hover:border-gold/40"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider ${style.badge}`}
                          data-testid="scene-type-chip"
                        >
                          {style.short}
                        </span>
                        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                          {formatClock(scene.start_time)}–{formatClock(scene.end_time)}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm leading-snug text-foreground" data-testid="scene-goal-text">
                        {scene.visual_goal}
                      </p>
                      {scene.visual_search_queries.length > 0 ? (
                        <p className="mt-1 flex items-start gap-1.5 font-mono text-[10px] leading-relaxed text-muted-foreground">
                          <Search className="mt-0.5 size-2.5 shrink-0" />
                          <span className="line-clamp-1">{scene.visual_search_queries.join(" · ")}</span>
                        </p>
                      ) : null}
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        {scene.important_text.slice(0, 3).map((text) => (
                          <span
                            key={text}
                            className="flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 font-heading text-[11px] font-semibold text-gold"
                          >
                            <Type className="size-2.5" />
                            {text}
                          </span>
                        ))}
                        {scene.sound_effect_suggestion ? (
                          <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
                            <Volume2 className="size-2.5" />
                            {scene.sound_effect_suggestion}
                          </span>
                        ) : null}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
