import { Link } from "react-router-dom";
import { Clapperboard } from "lucide-react";
import { StorageBadge } from "@/components/StorageBadge";

/** Shared studio header: brand + truthful storage state. */
export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-[1400px] items-center justify-between gap-4 px-4 sm:px-6">
        <Link to="/" data-testid="header-brand" className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Clapperboard className="size-4" />
          </span>
          <span className="leading-tight">
            <span className="block font-heading text-sm font-semibold tracking-[0.18em] text-foreground">
              CHRONICLE AI
            </span>
            <span className="block font-mono text-[10px] tracking-[0.22em] text-muted-foreground">
              DOCUMENTARY STUDIO
            </span>
          </span>
        </Link>
        <StorageBadge />
      </div>
    </header>
  );
}
