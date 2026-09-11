"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { qs } from "@/lib/api";
import { useApi, useDebounced } from "@/lib/hooks";
import type { Page, PatientListItem } from "@/lib/types";

/** Quick patient lookup by MRN or name. Results are already filtered server-side by the access policy. */
export function PatientSearch() {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const q = useDebounced(term.trim(), 250);
  const { data, loading } = useApi<Page<PatientListItem>>(q.length >= 2 ? `/patients${qs({ q, limit: 8 })}` : null);

  function go(id: number) {
    setOpen(false);
    setTerm("");
    router.push(`/patients/${id}`);
  }

  return (
    <div className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
      <input value={term} onChange={(e) => { setTerm(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => { if (e.key === "Enter" && data?.items[0]) go(data.items[0].id); }}
        placeholder="Find patient by MRN or name…" aria-label="Find patient"
        className="h-9 w-full rounded-md border border-slate-200 bg-slate-50 pl-8 pr-3 text-sm placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
      {open && q.length >= 2 && (
        <div className="absolute left-0 right-0 top-10 z-40 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
          {loading && !data && <div className="px-3 py-2 text-xs text-slate-500">Searching…</div>}
          {data && data.items.length === 0 && <div className="px-3 py-2 text-xs text-slate-500">No accessible patients match.</div>}
          {data?.items.map((p) => (
            <button key={p.id} onMouseDown={() => go(p.id)}
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-brand-50">
              <span><span className="font-medium text-slate-800">{p.full_name}</span> <span className="text-xs text-slate-500">{p.age}y {p.sex}</span></span>
              <span className="font-mono text-xs text-slate-500">{p.mrn}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
