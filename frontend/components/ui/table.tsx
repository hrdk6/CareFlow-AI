"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/format";

import { EmptyState, ErrorState, Skeleton } from "./feedback";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

export function DataTable<T extends { id: number | string }>({
  columns, rows, loading, error, onRetry, empty = "No records found", onRowClick, dense,
}: {
  columns: Column<T>[]; rows: T[] | undefined; loading?: boolean; error?: unknown; onRetry?: () => void;
  empty?: string; onRowClick?: (row: T) => void; dense?: boolean;
}) {
  if (error) return <div className="p-3"><ErrorState error={error} onRetry={onRetry} /></div>;
  if (loading && !rows) return <div className="p-4"><Skeleton lines={6} /></div>;
  if (!rows?.length) return <EmptyState title={empty} />;
  return (
    <div className={cn("scroll-thin overflow-x-auto", loading && "opacity-60")}>
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50/80">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={cn("whitespace-nowrap px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500", c.className)}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.id} onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(onRowClick && "cursor-pointer hover:bg-brand-50/40")}>
              {columns.map((c) => (
                <td key={c.key} className={cn("px-3 align-top text-slate-700", dense ? "py-1.5" : "py-2.5", c.className)}>
                  {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ total, limit, offset, onChange }: {
  total: number; limit: number; offset: number; onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button disabled={page <= 1} onClick={() => onChange(offset - limit)} aria-label="Previous page"
          className="rounded p-1 hover:bg-slate-100 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
        <span className="px-1 tabular-nums">Page {page} / {pages}</span>
        <button disabled={page >= pages} onClick={() => onChange(offset + limit)} aria-label="Next page"
          className="rounded p-1 hover:bg-slate-100 disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
      </div>
    </div>
  );
}
