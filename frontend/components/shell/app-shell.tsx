"use client";

import {
  Activity, BarChart3, Bot, CalendarDays, ClipboardList, FileText, FlaskConical, LayoutDashboard, LogOut,
  Menu, Pill, Settings, Shield, Stethoscope, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { IconButton } from "@/components/ui/button";
import { Spinner } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { cn } from "@/lib/format";

import { PatientSearch } from "./patient-search";

interface NavItem { href: string; label: string; icon: React.ElementType; perms?: string[]; anyOf?: string[] }

const NAV: { section: string; items: NavItem[] }[] = [
  { section: "Station", items: [{ href: "/", label: "Central station", icon: LayoutDashboard }] },
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
  return name.replace(/^Dr\.\s*/, "").split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

/** Hospital time (UTC in this demo, like every scheduled time in the app), as every monitor shows it.
 *  Rendered after mount so server and client agree. */
function StationClock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date());
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 15_000);
    return () => { clearTimeout(first); clearInterval(id); };
  }, []);
  return (
    <time
      className="tabular hidden items-baseline gap-1.5 font-display text-[15px] font-semibold tracking-[0.04em] text-ink-2 sm:flex"
      dateTime={now?.toISOString()}
      suppressHydrationWarning
    >
      {now ? now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) : "--:--"}
      <span className="text-[11px] tracking-[0.12em] text-faint">UTC</span>
    </time>
  );
}

function Rail({ onNavigate }: { onNavigate?: () => void }) {
  const { user, can, logout } = useAuth();
  const pathname = usePathname();
  const visible = (item: NavItem) =>
    (!item.perms || can(...item.perms)) && (!item.anyOf || item.anyOf.some((p) => can(p)));

  return (
    <div className="flex h-full flex-col border-r border-line bg-rail">
      <Link href="/" onClick={onNavigate} className="flex h-14 items-center gap-2 border-b border-line px-5">
        <Activity className="h-[18px] w-[18px] text-ok" strokeWidth={2.25} aria-hidden />
        <span className="font-display text-[17px] font-bold uppercase tracking-[0.12em] text-ink">CareFlow</span>
        <span className="font-display text-[17px] font-semibold uppercase tracking-[0.12em] text-accent">AI</span>
      </Link>

      <nav className="scroll-thin flex-1 overflow-y-auto px-2.5 pb-4" aria-label="Primary">
        {NAV.map((group) => {
          const items = group.items.filter(visible);
          if (!items.length) return null;
          return (
            <div key={group.section} className="mt-5">
              <div className="px-2.5 pb-1.5 font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
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
                      "group mt-px flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] transition-colors duration-150",
                      active ? "bg-raised text-ink" : "text-muted hover:bg-panel hover:text-ink",
                    )}
                  >
                    <Icon className={cn("h-4 w-4 shrink-0", active ? "text-accent" : "text-faint group-hover:text-ink-2")} aria-hidden />
                    <span className="flex-1">{item.label}</span>
                    {/* The lit key: a square lamp marks the active view. */}
                    <span className={cn("h-1.5 w-1.5 bg-accent transition-opacity", active ? "opacity-100" : "opacity-0")} aria-hidden />
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {user && (
        <div className="flex items-center gap-2.5 border-t border-line px-3 py-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-raised-2 font-display text-[13px] font-bold tracking-[0.04em] text-ink">
            {initials(user.full_name)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-ink">{user.full_name}</div>
            <div className="truncate font-display text-[11px] font-semibold uppercase tracking-[0.1em] text-accent">{ROLE_LABEL[user.role]}</div>
          </div>
          <IconButton size="sm" label="Sign out" onClick={logout}><LogOut className="h-4 w-4" /></IconButton>
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const [menu, setMenu] = useState(false); // the rail closes itself through onNavigate

  if (loading && !user) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Connecting to station" /></div>;
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 md:block">
        <Rail />
      </aside>

      {menu && (
        <div className="animate-fade-in fixed inset-0 z-50 bg-black/70 md:hidden" onMouseDown={() => setMenu(false)}>
          <div className="animate-slide-in h-full w-64 shadow-e3" onMouseDown={(e) => e.stopPropagation()}>
            <Rail onNavigate={() => setMenu(false)} />
          </div>
          <IconButton label="Close navigation" className="absolute right-3 top-3 text-ink" onClick={() => setMenu(false)}>
            <X className="h-5 w-5" />
          </IconButton>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-field px-4 md:px-6">
          <IconButton label="Open navigation" className="md:hidden" onClick={() => setMenu(true)}>
            <Menu className="h-5 w-5" />
          </IconButton>
          <PatientSearch />
          <div className="ml-auto flex items-center gap-4">
            <StationClock />
          </div>
        </header>

        {/* Standing advisory, styled as a monitor's technical notice: always present, never dismissible. */}
        <div role="note" className="flex items-center gap-2.5 border-b border-warn-edge bg-warn-tint px-4 py-1.5 md:px-6">
          <span className="h-2 w-2 shrink-0 bg-warn" aria-hidden />
          <p className="font-display text-[12px] font-semibold uppercase tracking-[0.08em] text-warn">
            Synthetic demonstration data <span className="text-warn/60">·</span> decision support only, not for clinical use
          </p>
        </div>

        <main className="mx-auto w-full max-w-[1560px] flex-1 px-4 py-6 md:px-6">{children}</main>
      </div>
    </div>
  );
}
