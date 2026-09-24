import { useQuery } from "@tanstack/react-query";
import { CircleCheck, HardDrive, TriangleAlert } from "lucide-react";
import { apiGet } from "@/lib/api";
import type { SystemStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: () => apiGet<SystemStatus>("/system/status"),
    retry: false,
    staleTime: 30_000,
  });
}

/** Setup instructions for connecting Cloudflare R2 (the only storage backend).
 * `children` must be a single element (a Button) — base-ui renders it as the real
 * trigger element, which keeps native button semantics. */
export function StorageSetupDialog({ children }: { children: React.ReactElement }) {
  return (
    <Dialog>
      <DialogTrigger render={children} />
      <DialogContent className="max-w-lg border-border bg-card">
        <DialogHeader>
          <DialogTitle className="font-heading">Connect Cloudflare R2</DialogTitle>
          <DialogDescription>
            Chronicle stores every upload in your own R2 bucket — nothing lands on local
            disk. Until the keys below are set, uploading stays disabled.
          </DialogDescription>
        </DialogHeader>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
          <li>
            Open the Cloudflare dashboard → <span className="text-foreground">R2 Object Storage</span> →
            create a bucket.
          </li>
          <li>Under “Manage API tokens” create a token with Object Read &amp; Write.</li>
          <li>
            Add these keys to <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-gold">backend/.env</code>:
            <pre className="mt-2 overflow-x-auto rounded-md border border-border bg-timeline p-3 font-mono text-xs leading-5 text-foreground">
{`R2_ACCOUNT_ID=…        # account id
R2_ACCESS_KEY_ID=…     # token access key
R2_SECRET_ACCESS_KEY=… # token secret
R2_BUCKET=…            # bucket name`}
            </pre>
          </li>
          <li>Restart the backend — the badge flips to “R2 connected”.</li>
        </ol>
      </DialogContent>
    </Dialog>
  );
}

/** Header pill that always tells the truth about object storage. */
export function StorageBadge() {
  const { data } = useSystemStatus();

  let label: string;
  let tone: "ok" | "warn" | "offline";
  if (!data) {
    label = "API offline";
    tone = "offline";
  } else if (data.storage.configured) {
    label = `R2 connected${data.storage.bucket ? ` · ${data.storage.bucket}` : ""}`;
    tone = "ok";
  } else {
    label = "Storage not configured";
    tone = "warn";
  }

  return (
    <StorageSetupDialog>
      <Button
        variant="outline"
        size="sm"
        data-testid="storage-status-badge"
        className={
          tone === "ok"
            ? "gap-2 border-emerald-500/30 text-emerald-300"
            : tone === "warn"
              ? "gap-2 border-amber-500/40 text-amber-300"
              : "gap-2"
        }
      >
        {tone === "ok" ? (
          <CircleCheck className="size-3.5 text-emerald-400" />
        ) : tone === "warn" ? (
          <TriangleAlert className="size-3.5 text-amber-400" />
        ) : (
          <HardDrive className="size-3.5 text-muted-foreground" />
        )}
        <span className="font-mono text-xs">{label}</span>
      </Button>
    </StorageSetupDialog>
  );
}
