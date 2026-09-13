import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";

import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/format";

import { Button } from "./button";

export function Spinner({ label = "Loading", className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn("flex items-center gap-2 text-sm text-muted", className)}>
      <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />
      {label}
    </div>
  );
}

export function Skeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2.5", className)} aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="shimmer h-3 rounded-sm" style={{ width: `${92 - (i % 3) * 16}%` }} />
      ))}
    </div>
  );
}

/** An empty channel: a quiet mark, a factual line, and at most one action. */
export function EmptyState({ title, message, icon, action }: {
  title: string; message?: string; icon?: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-2.5 text-faint">{icon ?? <Inbox className="h-5 w-5" />}</div>
      <p className="font-display text-[13px] font-semibold uppercase tracking-[0.08em] text-muted">{title}</p>
      {message && <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const requestId = (error as { requestId?: string })?.requestId;
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-md border border-high-edge bg-high-tint text-ink",
        compact ? "p-2.5 text-xs" : "p-3.5 text-sm",
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-high" aria-hidden />
      <div className="min-w-0 flex-1 leading-relaxed">
        <p>{errorMessage(error)}</p>
        {requestId && <p className="mt-1 font-mono text-[11px] text-muted">Request ID: {requestId}</p>}
      </div>
      {onRetry && (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}

export function Notice({ tone = "info", children, icon }: {
  tone?: "info" | "warning" | "success" | "danger"; children: React.ReactNode; icon?: React.ReactNode;
}) {
  const tones = {
    info: "border-info-edge bg-info-tint [&>svg]:text-info",
    warning: "border-warn-edge bg-warn-tint [&>svg]:text-warn",
    success: "border-ok-edge bg-ok-tint [&>svg]:text-ok",
    danger: "border-high-edge bg-high-tint [&>svg]:text-high",
  };
  return (
    <div className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-xs leading-relaxed text-ink", tones[tone])}>
      {icon}
      <div className="min-w-0">{children}</div>
    </div>
  );
}
