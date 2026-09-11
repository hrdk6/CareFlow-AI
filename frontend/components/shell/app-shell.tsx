"use client";

import {
  Activity, BarChart3, Bot, CalendarDays, ClipboardList, FileText, FlaskConical, LayoutDashboard, LogOut,
  Pill, Settings, Shield, Stethoscope, Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
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

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, can, logout } = useAuth();
  const pathname = usePathname();

  if (loading && !user) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Loading workspace" /></div>;
  }

  const visible = (item: NavItem) =>
    (!item.perms || can(...item.perms)) && (!item.anyOf || item.anyOf.some((p) => can(p)));

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900 text-slate-300 md:flex">
        <Link href="/" className="flex items-center gap-2 px-5 py-4 text-[15px] font-semibold text-white">
          <Activity className="h-5 w-5 text-brand-200" /> CareFlow AI
        </Link>
        <nav className="scroll-thin flex-1 overflow-y-auto px-3 pb-4">
          {NAV.map((group) => {
            const items = group.items.filter(visible);
            if (!items.length) return null;
            return (
              <div key={group.section} className="mt-4">
                <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{group.section}</div>
                {items.map((item) => {
                  const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                  const Icon = item.icon;
                  return (
                    <Link key={item.href} href={item.href}
                      className={cn("mt-0.5 flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] transition-colors",
                        active ? "bg-slate-800 text-white" : "hover:bg-slate-800/60 hover:text-white")}>
                      <Icon className={cn("h-4 w-4", active ? "text-brand-200" : "text-slate-500")} /> {item.label}
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </nav>
        {user && (
          <div className="border-t border-slate-800 px-4 py-3">
            <div className="truncate text-sm font-medium text-white">{user.full_name}</div>
            <div className="truncate text-xs text-slate-400">{user.email}</div>
            <button onClick={logout} className="mt-2 flex items-center gap-1.5 text-xs text-slate-400 hover:text-white">
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
        )}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="bg-amber-50 px-4 py-1 text-center text-[11px] text-amber-900 border-b border-amber-200">
          Synthetic demonstration data · AI output is decision support only — not for clinical use
        </div>
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-6">
          <PatientSearch />
          <div className="ml-auto flex items-center gap-3">
            {user && <Badge tone="brand">{ROLE_LABEL[user.role]}</Badge>}
            <button onClick={logout} className="rounded p-1.5 text-slate-500 hover:bg-slate-100 md:hidden" aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-6">{children}</main>
      </div>
    </div>
  );
}
