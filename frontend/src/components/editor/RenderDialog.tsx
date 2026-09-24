import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface RenderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Render console — the button exists, the engine honestly does not render yet. */
export default function RenderDialog({ open, onOpenChange }: RenderDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="render-dialog" className="max-w-md border-border bg-card">
        <DialogHeader>
          <DialogTitle className="font-heading">Render video</DialogTitle>
          <DialogDescription>
            Your AI scene plan is the input the renderer will consume. Asset resolution
            (stage 3) and the compositor (stage 4) are not built yet — nothing is
            rendered, and the app will never claim otherwise.
          </DialogDescription>
        </DialogHeader>
        <ul className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          {[
            "Real image & footage search",
            "Ken Burns photo moves",
            "Maps & chart graphics",
            "Kinetic typography",
            "Transitions & SFX",
            "1080p / 720p profiles",
          ].map((item) => (
            <li key={item} className="flex items-center gap-2 rounded-md border border-border/70 bg-timeline/60 px-2.5 py-2" data-testid="render-roadmap-item">
              <Badge variant="outline" className="h-1.5 w-1.5 rounded-full border-0 bg-gold p-0" />
              {item}
            </li>
          ))}
        </ul>
        <DialogFooter className="items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            available in a later stage
          </span>
          <Button variant="secondary" size="sm" data-testid="render-confirm-button" disabled>
            Start render
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
