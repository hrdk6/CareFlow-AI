"use client";

import {
  Activity, BarChart3, Bot, CalendarDays, ClipboardList, FileText, FlaskConical, LayoutDashboard, LogOut,
  Menu, Pill, Settings, Shield, ShieldAlert, Stethoscope, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { IconButton } from "@/components/ui/button";
import { Spinner } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { cn } from "@/lib/format";

import { PatientSearch } from "./patient-search";

interface NavItem { href: string; label: string; icon: React.ElementType; perms?: string[]; anyOf?: string[] }

const NAV: { section: string; items: NavItem[] }[] = [
  { section: "Overview", items: [{ href: "/", label: "Dashboard", icon: LayoutDashboard }] },
  {
    section: "Care", items: [
      { href: "/patients", label: "Patients", icon: Users },
      { href: "/appointments", label: "Appointments", icon: CalendarDays, perms: ["appointments:read"] },
      { href: "/doctors", label: "Doctors", icon: Stethoscope, perms: ["doctors:read"] },
    ],
  },
  {
    section: "Clinical", items: [
      { href: "/records", label: "Medical records", icon: ClipboardList, perms: [PERMS.clinical] },
      { href: "/prescriptions", label: "Prescriptions", icon: Pill, perms: [PERMS.clinical] },
      { href: "/labs", label: "Laboratory", icon: FlaskConical, perms: [PERMS.clinical] },
    ],
  },
  {
    section: "Intelligence", items: [
      { href: "/assistant", label: "AI assistant", icon: Bot, perms: [PERMS.ai] },
      { href: "/documents", label: "Knowledge base", icon: FileText, perms: [PERMS.docsRead] },
      { href: "/analytics", label: "ML analytics", icon: BarChart3, perms: [PERMS.ml] },
    ],
  },
  {
    section: "System", items: [
      { href: "/admin", label: "Administration", icon: Shield, anyOf: [PERMS.users, PERMS.audit, PERMS.observe] },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

const ROLE_LABEL = { ADMIN: "Administrator", DOCTOR: "Doctor", NURSE: "Nurse", RECEPTIONIST: "Reception" } as const;

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

function Rail({ onNavigate }: { onNavigate?: () => void }) {
  const { user, can, logout } = useAuth();
  const pathname = usePathname();
  const visible = (item: NavItem) =>
    (!item.perms || can(...item.perms)) && (!item.anyOf || item.anyOf.some((p) => can(p)));

  return (
    <div className="flex h-full flex-col bg-rail text-slate-300">
      <Link
        href="/"
        onClick={onNavigate}
        className="flex items-center gap-2.5 px-5 py-4 text-[15px] font-semibold tracking-tight text-white"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 shadow-e2">
          <Activity className="h-4 w-4 text-white" />
        </span>
        CareFlow<span className="-ml-1.5 font-normal text-brand-300">AI</span>
      </Link>

      <nav className="scroll-thin flex-1 overflow-y-auto px-3 pb-4">
        {NAV.map((group) => {
          const items = group.items.filter(visible);
          if (!items.length) return null;
          return (
            <div key={group.section} className="mt-5 first:mt-1">
              <div className="px-2.5 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                {group.section}
              </div>
              {items.map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group relative mt-0.5 flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium",
                      "transition-colors duration-150",
                      active ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white",
                    )}
                  >
                    {/* Accent bar marks the current page without shifting the row. */}
                    <span
                      className={cn(
                        "absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-400 transition-opacity duration-150",
                        active ? "opacity-100" : "opacity-0",
                      )}
                      aria-hidden
                    />
                    <Icon className={cn("h-4 w-4 shrink-0 transition-colors", active ? "text-brand-300" : "text-slate-500 group-hover:text-slate-300")} />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {user && (
        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-[11px] font-semibold text-white">
              {initials(user.full_name)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-white">{user.full_name}</div>
              <div className="truncate text-[11px] text-slate-500">{ROLE_LABEL[user.role]}</div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              aria-label="Sign out"
              className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-white/10 hover:text-white"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const [menu, setMenu] = useState(false);  // the rail closes itself through onNavigate

  if (loading && !user) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Loading workspace" /></div>;
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 md:block">
        <Rail />
      </aside>

      {/* Mobile navigation: the rail slides over the page instead of disappearing entirely. */}
      {menu && (
        <div className="animate-fade-in fixed inset-0 z-50 bg-slate-950/50 backdrop-blur-[2px] md:hidden" onMouseDown={() => setMenu(false)}>
          <div className="animate-slide-in h-full w-64 shadow-e3" onMouseDown={(e) => e.stopPropagation()}>
            <Rail onNavigate={() => setMenu(false)} />
          </div>
          <button
            onClick={() => setMenu(false)}
            aria-label="Close navigation"
            className="absolute right-4 top-4 rounded-lg p-2 text-white/80 hover:bg-white/10"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-center gap-2 border-b border-amber-200/70 bg-amber-50 px-4 py-1.5 text-center text-[11px] font-medium text-amber-900">
          <ShieldAlert className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>Synthetic demonstration data · AI output is decision support only — not for clinical use</span>
        </div>

        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-white/85 px-4 backdrop-blur-md md:px-6">
          <IconButton label="Open navigation" className="md:hidden" onClick={() => setMenu(true)}>
            <Menu className="h-5 w-5" />
          </IconButton>
          <PatientSearch />
          <div className="ml-auto flex items-center gap-2.5">
            {user && <Badge tone="brand" dot>{ROLE_LABEL[user.role]}</Badge>}
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-6 md:px-8 md:py-7">{children}</main>
      </div>
    </div>
  );
}
