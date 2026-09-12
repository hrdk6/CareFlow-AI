"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { qs } from "@/lib/api";
import { useApi, useDebounced } from "@/lib/hooks";
import type { Page, PatientListItem } from "@/lib/types";

/** Quick patient lookup by MRN or name. Results are already filtered server-side by the access policy. */
export function PatientSearch() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const q = useDebounced(term.trim(), 250);
  const { data, loading } = useApi<Page<PatientListItem>>(q.length >= 2 ? `/patients${qs({ q, limit: 8 })}` : null);

  // "/" focuses search the way it does in developer tools, without stealing keystrokes from a form.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement;
      const typing = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement;
      if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function go(id: number) {
    setOpen(false);
    setTerm("");
    input.current?.blur();
    router.push(`/patients/${id}`);
  }

  return (
    <div className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        ref={input}
        value={term}
        onChange={(e) => { setTerm(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && data?.items[0]) go(data.items[0].id);
          if (e.key === "Escape") input.current?.blur();
        }}
        placeholder="Find patient by MRN or name…"
        aria-label="Find patient"
        className="h-9 w-full rounded-lg border border-transparent bg-slate-100/80 pl-9 pr-10 text-sm text-slate-800 transition-colors duration-150 placeholder:text-slate-400 hover:bg-slate-100 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-brand-500/12"
      />
      {!term && (
        <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-line-strong bg-white px-1.5 py-0.5 font-mono text-[10px] text-slate-400 sm:block">
          /
        </kbd>
      )}
      {open && q.length >= 2 && (
        <div className="animate-pop-in absolute left-0 right-0 top-11 z-40 overflow-hidden rounded-xl border border-line bg-surface shadow-e3">
          {loading && !data && <div className="px-3 py-2.5 text-xs text-muted">Searching…</div>}
          {data && data.items.length === 0 && (
            <div className="px-3 py-2.5 text-xs text-muted">No accessible patients match.</div>
          )}
          {data?.items.map((p) => (
            <button
              key={p.id}
              onMouseDown={() => go(p.id)}
              className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-brand-50/70"
            >
              <span className="min-w-0 truncate">
                <span className="font-medium text-slate-800">{p.full_name}</span>{" "}
                <span className="text-xs text-muted">{p.age}y {p.sex}</span>
              </span>
              <span className="shrink-0 font-mono text-xs text-slate-500">{p.mrn}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
