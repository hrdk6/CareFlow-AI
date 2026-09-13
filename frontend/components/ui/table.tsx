"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/format";

import { IconButton } from "./button";
import { EmptyState, ErrorState, Skeleton } from "./feedback";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

/** Hairline rows, quiet sentence-case headings, values in tabular figures. */
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
    <div className={cn("scroll-thin overflow-x-auto transition-opacity duration-200", loading && "opacity-50")}>
      <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cn(
                  "sticky top-0 z-10 whitespace-nowrap border-b border-line bg-sunken px-3 py-2.5",
                  "text-xs font-medium text-muted",
                  c.className,
                )}
              >
                {c.header}
              </th>
            ))}
            {onRowClick && <th scope="col" className="sticky top-0 z-10 border-b border-line bg-sunken"><span className="sr-only">Open</span></th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              // Rows that open something are reachable by keyboard, not only by pointer.
              tabIndex={onRowClick ? 0 : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onRowClick(row); } } : undefined}
              className={cn(
                "transition-colors duration-100",
                onRowClick && "group cursor-pointer hover:bg-sunken focus-visible:bg-sunken focus-visible:outline-offset-[-2px]",
              )}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={cn("border-b border-line px-3 align-middle text-ink-2", dense ? "py-2" : "py-2.5", c.className)}
                >
                  {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "—")}
                </td>
              ))}
              {onRowClick && (
                <td className="w-10 border-b border-line pr-3 text-right align-middle">
                  <ChevronRight className="ml-auto h-4 w-4 text-line-strong transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-accent group-focus-visible:text-accent" aria-hidden />
                </td>
              )}
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
    <div className="flex items-center justify-between border-t border-line px-5 py-2.5 text-[13px] text-muted">
      <span className="tabular">
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="flex items-center gap-1">
        <IconButton size="sm" label="Previous page" disabled={page <= 1} onClick={() => onChange(offset - limit)}>
          <ChevronLeft className="h-4 w-4" />
        </IconButton>
        <span className="tabular px-1">Page {page} / {pages}</span>
        <IconButton size="sm" label="Next page" disabled={page >= pages} onClick={() => onChange(offset + limit)}>
          <ChevronRight className="h-4 w-4" />
        </IconButton>
      </div>
    </div>
  );
}
