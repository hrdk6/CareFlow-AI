"use client";

import {
  Activity, BarChart3, BedDouble, Bot, CalendarDays, ClipboardList, FileText, FlaskConical, Info, LayoutDashboard, LogOut,
  Menu, Pill, ScanLine, Settings, Shield, Stethoscope, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { initials } from "@/components/ui/avatar";
import { IconButton } from "@/components/ui/button";
import { ErrorState, Spinner } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { cn } from "@/lib/format";

import { PatientSearch } from "./patient-search";
import { RailStreams } from "./rail-streams";

interface NavItem { href: string; label: string; icon: React.ElementType; perms?: string[]; anyOf?: string[] }

const NAV: { section: string; items: NavItem[] }[] = [
  { section: "Overview", items: [{ href: "/", label: "Dashboard", icon: LayoutDashboard }] },
  {
    section: "Care", items: [
      { href: "/patients", label: "Patients", icon: Users },
      { href: "/ward", label: "Inpatients", icon: BedDouble, perms: [PERMS.clinical] },
      { href: "/imaging", label: "Radiology", icon: ScanLine, perms: [PERMS.clinical] },
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
      { href: "/analytics", label: "Model performance", icon: BarChart3, perms: [PERMS.ml] },
    ],
  },
  {
    section: "Hospital", items: [
      { href: "/admin", label: "Administration", icon: Shield, anyOf: [PERMS.users, PERMS.audit, PERMS.observe] },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

const ROLE_LABEL = { ADMIN: "Administrator", DOCTOR: "Doctor", NURSE: "Nurse", RECEPTIONIST: "Reception" } as const;

/** The sidebar wordmark from the Stitch design: a teal pulse tile beside "CareFlow AI" in Inter. */
function RailWordmark() {
  return (
    <span className="flex items-center gap-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#11998e] text-white shadow-sm shadow-teal-900/40 transition-transform duration-200 group-hover:scale-105">
        <Activity className="h-5 w-5" strokeWidth={2.5} aria-hidden />
      </span>
      <span className="font-sans text-lg font-bold tracking-tight text-white">
        CareFlow <span className="ml-0.5 text-base font-medium text-[#2dd4bf]">AI</span>
      </span>
    </span>
  );
}

function Rail({ onNavigate }: { onNavigate?: () => void }) {
  const { user, can, logout } = useAuth();
  const pathname = usePathname();
  const visible = (item: NavItem) =>
    (!item.perms || can(...item.perms)) && (!item.anyOf || item.anyOf.some((p) => can(p)));

  return (
    <div className="relative flex h-full select-none flex-col overflow-hidden border-r border-[#0e2a2e] bg-gradient-to-b from-[#07191c] via-[#0a2529] to-[#051518] font-sans text-slate-300">
      <RailStreams />

      <Link href="/" onClick={onNavigate} className="group relative z-10 flex h-16 shrink-0 items-center border-b border-[#0d2e33]/60 px-6">
        <RailWordmark />
      </Link>

      <nav className="scroll-rail relative z-10 flex-1 space-y-6 overflow-y-auto px-3 py-4" aria-label="Primary">
        {NAV.map((group) => {
          const items = group.items.filter(visible);
          if (!items.length) return null;
          return (
            <div key={group.section}>
              {/* Uppercase group labels are the Stitch sidebar's own voice; the rest of the app stays sentence case. */}
              <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-teal-200/60">{group.section}</p>
              <div className="space-y-1">
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
                        "group flex items-center gap-3 rounded-xl border px-3 py-2 text-sm font-medium transition-all duration-200",
                        active
                          ? "border-teal-500/20 bg-[#0f343a]/90 text-white shadow-sm shadow-teal-950/40 hover:bg-[#133f47]"
                          : "border-transparent text-slate-300 hover:bg-[#0c2b30]/70 hover:text-white",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-5 w-5 shrink-0 transition-[color,opacity] duration-150",
                          active ? "text-[#2dd4bf]" : "opacity-75 group-hover:opacity-100",
                        )}
                        strokeWidth={1.8}
                        aria-hidden
                      />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {user && (
        <div className="relative z-10 border-t border-[#0e2a2e] bg-[#051518]/90 p-3 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-2 rounded-xl p-2 transition-colors duration-150 hover:bg-[#0c2b30]/70">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-emerald-700/50 bg-emerald-950/80 text-sm font-semibold text-emerald-400">
                {initials(user.full_name)}
              </span>
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-sm font-semibold leading-tight text-white">{user.full_name}</span>
                <span className="truncate text-xs text-slate-400">{ROLE_LABEL[user.role]}</span>
              </div>
            </div>
            <button type="button" onClick={logout} aria-label="Sign out" title="Sign out"
              className="shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:bg-white/5 hover:text-white">
              <LogOut className="h-5 w-5" strokeWidth={1.8} aria-hidden />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, error, retry } = useAuth();
  const [menu, setMenu] = useState(false); // the rail closes itself through onNavigate

  if (loading && !user) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Loading your workspace" /></div>;
  }

  // Without a user there are no permissions to build the menu from, so explain the failure instead of
  // rendering an empty workspace. (An expired session never gets here: the API client sends it to sign-in.)
  if (!user && error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-6 shadow-e2">
          <h1 className="text-[20px] font-semibold text-ink">Your workspace could not load</h1>
          <p className="mt-1 mb-4 text-sm text-muted">CareFlow could not check your session.</p>
          <ErrorState error={error} onRetry={retry} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 lg:block">
        <Rail />
      </aside>

      {menu && (
        <div className="animate-fade-in fixed inset-0 z-50 bg-[#0e2326]/45 lg:hidden" onMouseDown={() => setMenu(false)}>
          <div className="animate-slide-in h-full w-72 shadow-e3" onMouseDown={(e) => e.stopPropagation()}>
            <Rail onNavigate={() => setMenu(false)} />
          </div>
          <IconButton label="Close navigation" className="absolute right-3 top-3 text-white hover:bg-white/15 hover:text-white" onClick={() => setMenu(false)}>
            <X className="h-5 w-5" />
          </IconButton>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-panel/90 px-4 backdrop-blur-md md:px-8">
          <IconButton label="Open navigation" className="lg:hidden" onClick={() => setMenu(true)}>
            <Menu className="h-5 w-5" />
          </IconButton>
          <PatientSearch />
          <p role="note" className="ml-auto hidden items-center gap-1.5 rounded-full bg-warn-tint px-3 py-1 text-xs font-medium text-warn ring-1 ring-inset ring-warn-edge xl:flex">
            <Info className="h-3.5 w-3.5" aria-hidden />
            Demo with synthetic patients · not for clinical use
          </p>
        </header>
        {/* The advisory stays visible on every screen; below xl it drops out of the header into its own line. */}
        <p role="note" className="flex items-center justify-center gap-1.5 border-b border-warn-edge bg-warn-tint px-4 py-1.5 text-center text-xs font-medium text-warn xl:hidden">
          <Info className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Demo with synthetic patients · not for clinical use
        </p>

        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}
