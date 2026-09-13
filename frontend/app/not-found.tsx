import { ArrowLeft, Compass } from "lucide-react";
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-field px-6 py-16">
      <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-8 text-center shadow-e2">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-accent-tint text-accent">
          <Compass className="h-6 w-6" aria-hidden />
        </span>
        <h1 className="mt-5 text-[24px] font-semibold text-ink">This page doesn&apos;t exist</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          The link may be mistyped, or the page may have moved. Head back to the dashboard to carry on.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-medium text-on-signal transition-colors hover:bg-accent-strong"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden /> Back to dashboard
        </Link>
      </div>
    </main>
  );
}
