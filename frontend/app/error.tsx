"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

/** Last-resort boundary for an unexpected rendering failure. API errors are handled inline on each page. */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-field px-6 py-16">
      <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-8 text-center shadow-e2">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-high-tint text-high">
          <AlertTriangle className="h-6 w-6" aria-hidden />
        </span>
        <h1 className="mt-5 text-[24px] font-semibold text-ink">Something went wrong</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          This screen hit an unexpected problem. Try again, or go back to the dashboard.
        </p>
        {error.digest && <p className="mt-3 font-mono text-xs text-faint">Reference: {error.digest}</p>}
        <div className="mt-6 flex justify-center gap-2">
          <button
            onClick={reset}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-medium text-on-signal transition-colors hover:bg-accent-strong"
          >
            <RefreshCw className="h-4 w-4" aria-hidden /> Try again
          </button>
          <Link
            href="/"
            className="inline-flex h-10 items-center rounded-lg bg-panel px-4 text-sm font-medium text-ink shadow-e1 ring-1 ring-inset ring-line-strong transition-colors hover:bg-sunken"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
