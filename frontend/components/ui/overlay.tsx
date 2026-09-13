"use client";

import { X } from "lucide-react";
import { useEffect } from "react";

import { cn } from "@/lib/format";

import { IconButton } from "./button";

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);
}

/** Locks background scroll while an overlay is open, so the page behind does not drift. */
function useScrollLock(open: boolean) {
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);
}

export function Modal({ open, onClose, title, children, footer, wide }: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean;
}) {
  useEscape(open, onClose);
  useScrollLock(open);
  if (!open) return null;
  return (
    <div
      className="animate-fade-in fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#0e2326]/40 p-4 pt-[7vh]"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(e) => e.stopPropagation()}
        className={cn(
          "animate-pop-in w-full rounded-2xl border border-line bg-panel shadow-e3",
          wide ? "max-w-3xl" : "max-w-lg",
        )}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
          <h2 className="text-[17px] font-semibold text-ink">{title}</h2>
          <IconButton size="sm" label="Close" onClick={onClose}><X className="h-4 w-4" /></IconButton>
        </div>
        <div className="px-6 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 rounded-b-2xl border-t border-line bg-sunken px-6 py-3.5">{footer}</div>}
      </div>
    </div>
  );
}

export function Drawer({ open, onClose, title, subtitle, children }: {
  open: boolean; onClose: () => void; title: string; subtitle?: React.ReactNode; children: React.ReactNode;
}) {
  useEscape(open, onClose);
  useScrollLock(open);
  if (!open) return null;
  return (
    <div className="animate-fade-in fixed inset-0 z-50 flex justify-end bg-[#0e2326]/35" onMouseDown={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(e) => e.stopPropagation()}
        className="animate-slide-in flex h-full w-full max-w-xl flex-col border-l border-line bg-panel shadow-e3"
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-[17px] font-semibold text-ink">{title}</h2>
            {subtitle && <div className="mt-1 text-xs text-muted">{subtitle}</div>}
          </div>
          <IconButton size="sm" label="Close" onClick={onClose}><X className="h-4 w-4" /></IconButton>
        </div>
        <div className="scroll-thin flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </aside>
    </div>
  );
}
