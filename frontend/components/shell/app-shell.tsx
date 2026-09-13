"use client";

import {
  Activity, BarChart3, Bot, CalendarDays, ClipboardList, FileText, FlaskConical, Info, LayoutDashboard, LogOut,
  Menu, Pill, Settings, Shield, Stethoscope, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

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

export function initials(name: string): string {
  return name.replace(/^Dr\.\s*/, "").split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

export function Wordmark({ tone = "dark", size = "md" }: { tone?: "dark" | "light"; size?: "md" | "lg" }) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        className={cn(
          "flex shrink-0 items-center justify-center rounded-[10px] bg-accent text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]",
          size === "lg" ? "h-9 w-9" : "h-8 w-8",
        )}
      >
        <Activity className={size === "lg" ? "h-5 w-5" : "h-[18px] w-[18px]"} strokeWidth={2.25} aria-hidden />
      </span>
      <span
        className={cn(
          "font-display font-semibold tracking-[-0.01em]",
          size === "lg" ? "text-[20px]" : "text-[17px]",
          tone === "light" ? "text-white" : "text-ink",
        )}
      >
        CareFlow <span className={tone === "light" ? "text-[#7fd8c8]" : "text-accent"}>AI</span>
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
    <div className="flex h-full flex-col bg-rail text-rail-ink">
      <Link href="/" onClick={onNavigate} className="flex h-16 items-center px-5">
        <Wordmark tone="light" />
      </Link>

      <nav className="scroll-rail flex-1 overflow-y-auto px-3 pb-4" aria-label="Primary">
        {NAV.map((group) => {
          const items = group.items.filter(visible);
          if (!items.length) return null;
          return (
            <div key={group.section} className="mt-5 first:mt-2">
              <div className="px-3 pb-1.5 text-[11px] font-medium text-rail-muted">{group.section}</div>
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
                      "group mt-0.5 flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors duration-150",
                      active ? "bg-rail-2 text-white" : "text-[#bcd0d1] hover:bg-white/[0.06] hover:text-white",
                    )}
                  >
                    <Icon
                      className={cn("h-[18px] w-[18px] shrink-0 transition-colors", active ? "text-[#7fd8c8]" : "text-rail-muted group-hover:text-[#d6e6e5]")}
                      aria-hidden
                    />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {user && (
        <div className="m-3 flex items-center gap-3 rounded-xl bg-white/[0.05] px-3 py-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#1f4a4a] text-[12px] font-semibold text-[#c9efe7]">
            {initials(user.full_name)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-white">{user.full_name}</div>
            <div className="truncate text-[12px] text-rail-muted">{ROLE_LABEL[user.role]}</div>
          </div>
          <IconButton size="sm" label="Sign out" onClick={logout} className="text-rail-muted hover:bg-white/10 hover:text-white">
            <LogOut className="h-4 w-4" />
          </IconButton>
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const [menu, setMenu] = useState(false); // the rail closes itself through onNavigate

  if (loading && !user) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Loading your workspace" /></div>;
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
