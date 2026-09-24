import {
  Clapperboard,
  Film,
  Play,
  Quote,
  Search,
  Sparkles,
  Type,
  Volume2,
  Wand2,
} from "lucide-react";
import { formatClock } from "@/lib/format";
import { humanizeToken, sceneStyle } from "@/lib/sceneStyles";
import type { Scene } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface SceneInspectorProps {
  scene: Scene | null;
  onOpenChange: (open: boolean) => void;
  onPlayScene: (scene: Scene) => void;
}

function Field({
  icon: Icon,
  label,
  children,
  testid,
}: {
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
  testid: string;
}) {
  return (
    <div data-testid={testid}>
      <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        <Icon className="size-3 text-gold" />
        {label}
      </p>
      <div className="mt-1.5 text-sm leading-relaxed text-foreground/90">{children}</div>
    </div>
  );
}

/** Full structured visual plan for one scene — every field the AI produced. */
export default function SceneInspector({ scene, onOpenChange, onPlayScene }: SceneInspectorProps) {
  if (!scene) return null;
  const style = sceneStyle(scene.scene_type);

  return (
    <Dialog open={Boolean(scene)} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="scene-inspector"
        className="max-h-[88svh] max-w-2xl overflow-y-auto border-border bg-card"
      >
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className={`font-mono text-[10px] uppercase tracking-wider ${style.badge}`}
              data-testid="scene-inspector-type"
            >
              {style.label}
            </Badge>
            <span
              className="font-mono text-[11px] tabular-nums text-muted-foreground"
              data-testid="scene-inspector-time"
            >
              {formatClock(scene.start_time)} → {formatClock(scene.end_time)} ·{" "}
              {(scene.end_time - scene.start_time).toFixed(1)}s
            </span>
            <span className="font-mono text-[11px] text-muted-foreground">
              scene {scene.index + 1}
            </span>
          </div>
          <DialogTitle className="mt-1 font-heading text-lg leading-snug" data-testid="scene-inspector-goal">
            {scene.visual_goal}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          <Field icon={Quote} label="Narration" testid="scene-inspector-transcript">
            <p className="rounded-lg border border-border/70 bg-timeline/70 px-3 py-2.5 italic text-foreground/85">
              “{scene.transcript_text}”
            </p>
          </Field>

          <Field icon={Search} label="Visual search queries" testid="scene-inspector-queries">
            {scene.visual_search_queries.length > 0 ? (
              <ul className="flex flex-wrap gap-2">
                {scene.visual_search_queries.map((query) => (
                  <li
                    key={query}
                    data-testid="scene-inspector-query"
                    className="rounded-md border border-gold/30 bg-gold/5 px-2.5 py-1 font-mono text-xs text-amber-100"
                  >
                    {query}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                None — this visual is generated, not searched.
              </p>
            )}
          </Field>

          <Field icon={Wand2} label="Suggested treatment" testid="scene-inspector-treatment">
            {scene.suggested_visual_treatment}
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field icon={Type} label="On-screen emphasis" testid="scene-inspector-important-text">
              {scene.important_text.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {scene.important_text.map((text) => (
                    <span
                      key={text}
                      className="rounded border border-border bg-muted px-2 py-0.5 font-heading text-sm font-semibold text-gold"
                    >
                      {text}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-sm text-muted-foreground">Nothing emphasised</span>
              )}
            </Field>

            <Field icon={Volume2} label="Sound effect" testid="scene-inspector-sfx">
              {scene.sound_effect_suggestion ?? (
                <span className="text-muted-foreground">Silence suits this beat</span>
              )}
            </Field>

            <Field icon={Film} label="Animation" testid="scene-inspector-animation">
              <span className="font-mono text-xs text-foreground">{humanizeToken(scene.animation_type)}</span>
            </Field>

            <Field icon={Clapperboard} label="Transition in" testid="scene-inspector-transition">
              <span className="font-mono text-xs text-foreground">{humanizeToken(scene.transition_type)}</span>
            </Field>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-4">
            <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              <Sparkles className="size-3 text-gold" />
              assets are attached in stage 3 — nothing is downloaded yet
            </p>
            <Button
              size="sm"
              variant="secondary"
              data-testid="scene-inspector-play-button"
              onClick={() => onPlayScene(scene)}
            >
              <Play className="size-3.5" />
              Play this scene
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
