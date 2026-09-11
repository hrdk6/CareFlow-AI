import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";

import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/format";

import { Button } from "./button";

export function Spinner({ label = "Loading", className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn("flex items-center gap-2 text-sm text-slate-500", className)}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function Skeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)} aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3.5 animate-pulse rounded bg-slate-100" style={{ width: `${90 - (i % 3) * 15}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({ title, message, icon, action }: {
  title: string; message?: string; icon?: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        {icon ?? <Inbox className="h-5 w-5" />}
      </div>
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {message && <p className="mt-1 max-w-sm text-xs text-slate-500">{message}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const requestId = (error as { requestId?: string })?.requestId;
  return (
    <div role="alert" className={cn("flex items-start gap-3 rounded-md border border-rose-200 bg-rose-50 text-rose-800", compact ? "p-2.5 text-xs" : "p-4 text-sm")}>
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <p>{errorMessage(error)}</p>
        {requestId && <p className="mt-1 font-mono text-[11px] text-rose-600">Request ID: {requestId}</p>}
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
    info: "border-sky-200 bg-sky-50 text-sky-900", warning: "border-amber-200 bg-amber-50 text-amber-900",
    success: "border-emerald-200 bg-emerald-50 text-emerald-900", danger: "border-rose-200 bg-rose-50 text-rose-900",
  };
  return (
    <div className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-xs leading-relaxed", tones[tone])}>
      {icon}
      <div className="min-w-0">{children}</div>
    </div>
  );
}
