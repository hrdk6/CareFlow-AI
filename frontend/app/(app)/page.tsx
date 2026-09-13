"use client";

import {
  AlertCircle, ArrowRight, BedDouble, Bot, CalendarClock, ChevronRight, DoorOpen, FileText, FlaskConical,
  MessageSquareText, ShieldOff, Users,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtDate, fmtTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";

interface CriticalResult {
  id: number; patient_id: number; mrn: string; name: string; test: string; code: string; value: number | null;
  value_text: string | null; unit: string | null; reference_low: number | null; reference_high: number | null; collected_at: string;
}

interface Dashboard {
  role: string; role_label: string; patients_visible: number; generated_at?: string;
  appointments_today?: { id: number; time: string; patient: string; patient_id: number; mrn: string; doctor: string; reason: string; status: string }[];
  appointments_today_count?: number; inpatients?: number; discharges_7d?: number; discharges_30d?: number;
  documents_indexed?: number; ai_queries_24h?: number; denied_events_24h?: number;
  critical_results?: CriticalResult[]; critical_results_7d?: number; abnormal_results_7d?: number;
  census?: { patient_id: number; mrn: string; name: string; reason: string; admitted_at: string; department: string; ward: string | null }[];
  recent_discharges?: { patient_id: number; mrn: string; name: string; reason: string; discharged_at: string; disposition: string }[];
}

const REFRESH_MS = 60_000;

function ago(iso: string, now: number): string {
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function dayOfStay(admittedAt: string, now: number): number {
  return Math.max(1, Math.floor((now - new Date(admittedAt).getTime()) / 86_400_000) + 1);
}

function resultValue(r: CriticalResult): string {
  return r.value !== null ? `${r.value}${r.unit ? ` ${r.unit}` : ""}` : r.value_text ?? "—";
}

/** How far a result sits outside its reference range, in range-widths. Orders the attention list. */
function severity(r: CriticalResult): number {
  if (r.value === null || r.reference_low === null || r.reference_high === null) return 0;
  const width = r.reference_high - r.reference_low || 1;
  return Math.max((r.reference_low - r.value) / width, (r.value - r.reference_high) / width, 0);
}

function greeting(now: number): string {
  const hour = new Date(now).getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

function firstName(fullName: string | undefined): string {
  if (!fullName) return "";
  const trimmed = fullName.trim();
  const parts = trimmed.split(/\s+/);
  if (/^Dr\.?$/i.test(parts[0])) return `Dr. ${parts[parts.length - 1]}`;
  return parts[0];
}

function Avatar({ name, tone = "neutral" }: { name: string; tone?: "neutral" | "alert" }) {
  const letters = name.replace(/^Dr\.\s*/, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
  return (
    <span
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold",
        tone === "alert" ? "bg-high-tint text-high ring-1 ring-inset ring-high-edge" : "bg-accent-tint text-accent",
      )}
      aria-hidden
    >
      {letters}
    </span>
  );
}

/** A card section with a title row and an optional link out. */
function Panel({ title, count, description, href, linkLabel, className, children, id, style }: {
  title: string; count?: number; description?: string; href?: string; linkLabel?: string; className?: string;
  children: React.ReactNode; id?: string; style?: React.CSSProperties;
}) {
  return (
    <section id={id} style={style} className={cn("rise min-w-0 overflow-hidden rounded-xl border border-line bg-panel shadow-e1", className)}>
      <header className="flex items-center justify-between gap-3 px-5 pb-3 pt-4">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-[16px] font-semibold text-ink">
            {title}
            {count !== undefined && (
              <span className="tabular rounded-full bg-raised px-2 text-[12px] font-medium leading-5 text-muted">{count}</span>
            )}
          </h2>
          {description && <p className="mt-0.5 truncate text-[13px] text-muted">{description}</p>}
        </div>
        {href && (
          <Link href={href} className="group flex shrink-0 items-center gap-1 rounded-md text-[13px] font-medium text-accent hover:text-accent-strong">
            {linkLabel ?? "View all"}
            <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden />
          </Link>
        )}
      </header>
      {children}
    </section>
  );
}

/** A summary figure. Colour is spent only when the figure itself is a status. */
function Summary({ label, value, context, icon: Icon, href, tone, i }: {
  label: string; value: number | undefined; context: React.ReactNode; icon: React.ElementType; href?: string;
  tone?: "high"; i: number;
}) {
  const alert = tone === "high" && (value ?? 0) > 0;
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-start gap-2 text-[12px] font-medium text-muted sm:items-center sm:text-[13px]">
          <Icon className={cn("h-4 w-4 shrink-0", alert ? "text-high" : "text-faint")} aria-hidden />
          <span className="leading-tight sm:truncate">{label}</span>
        </span>
        {href && <ChevronRight className="hidden h-4 w-4 shrink-0 sm:block text-line-strong transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden />}
      </div>
      <div className={cn("tabular mt-3 font-display text-[28px] font-semibold leading-none tracking-[-0.02em] sm:text-[34px]", alert ? "text-high" : "text-ink")}>
        {value ?? "—"}
      </div>
      <div className="mt-2 line-clamp-2 text-[12px] text-muted sm:truncate sm:text-[13px]">{context}</div>
    </>
  );
  const cls = "rise group block min-w-0 rounded-xl border border-line bg-panel px-4 py-4 shadow-e1 sm:px-5";
  const style = { "--i": i } as React.CSSProperties;
  return href ? (
    <Link href={href} style={style} className={cn(cls, "transition-[box-shadow,border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-e2")}>
      {body}
    </Link>
  ) : (
    <div style={style} className={cls}>{body}</div>
  );
}

/** Critical lab results, most out-of-range first. Shown only when there is something to act on. */
function Attention({ data, now }: { data: Dashboard; now: number }) {
  const results = [...(data.critical_results ?? [])].sort(
    (a, b) => severity(b) - severity(a) || new Date(b.collected_at).getTime() - new Date(a.collected_at).getTime(),
  );
  if (results.length === 0) return null;
  const total = data.critical_results_7d ?? results.length;
  return (
    <section aria-label="Critical results" className="rise overflow-hidden rounded-xl border border-high-edge bg-panel shadow-e1" style={{ "--i": 0 } as React.CSSProperties}>
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 bg-high-tint px-5 py-3">
        <span className="attention-dot h-2 w-2 shrink-0 rounded-full bg-high text-high" aria-hidden />
        <h2 className="text-[15px] font-semibold text-ink">
          {total} critical lab {total === 1 ? "result needs" : "results need"} review
        </h2>
        <span className="text-[13px] text-[#9e3049]">from the last 7 days</span>
        <Link href="/labs" className="group ml-auto flex items-center gap-1 text-[13px] font-medium text-high hover:underline">
          All lab results <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      </header>
      <ul className="grid grid-cols-1 divide-y divide-line md:grid-cols-2 md:divide-y-0">
        {results.map((r, idx) => (
          <li key={r.id} className={cn("min-w-0 md:border-t md:border-line", idx < 2 && "md:border-t-0", idx % 2 === 0 && "md:border-r")}>
            <Link href={`/patients/${r.patient_id}?tab=labs`} className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-sunken sm:px-5">
              <Avatar name={r.name} tone="alert" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-ink">{r.name}</span>
                <span className="block truncate text-[13px] text-muted">
                  {r.test}
                  {r.reference_low !== null && r.reference_high !== null && (
                    <span className="hidden sm:inline"> · normal {r.reference_low}–{r.reference_high}</span>
                  )}
                  {" · "}{ago(r.collected_at, now)}
                </span>
              </span>
              <span className="tabular shrink-0 rounded-lg bg-high-tint px-2.5 py-1 text-[13px] font-semibold text-high ring-1 ring-inset ring-high-edge">
                {resultValue(r)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Row({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) {
  return (
    <li className="border-t border-line first:border-t-0">
      <Link href={href} className={cn("group flex items-center gap-3 px-5 py-3 transition-colors duration-150 hover:bg-sunken", className)}>
        {children}
        <ChevronRight className="h-4 w-4 shrink-0 text-line-strong transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden />
      </Link>
    </li>
  );
}

export default function DashboardPage() {
  const { user, can } = useAuth();
  const { data, error, loading, reload } = useApi<Dashboard>("/dashboard");
  const [now, setNow] = useState(() => Date.now());

  // Keep the figures current during a shift without a manual reload.
  useEffect(() => {
    const refresh = setInterval(reload, REFRESH_MS);
    const clock = setInterval(() => setNow(Date.now()), 30_000);
    return () => { clearInterval(refresh); clearInterval(clock); };
  }, [reload]);

  const clinical = can(PERMS.clinical);
  const riskTab = can(PERMS.ml) ? "predictions" : "overview";
  const flagged = new Map<number, CriticalResult>();
  for (const r of data?.critical_results ?? []) {
    const known = flagged.get(r.patient_id);
    if (!known || severity(r) > severity(known)) flagged.set(r.patient_id, r);
  }
  const today = new Date(now).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  const summaries = data ? [
    !clinical && { label: "Registered patients", value: data.patients_visible, icon: Users, href: "/patients",
      context: "Search or register from Patients" },
    clinical && { label: "Admitted patients", value: data.inpatients, icon: BedDouble, href: "#admitted",
      context: `${data.discharges_7d ?? 0} discharged this week` },
    data.appointments_today_count !== undefined && { label: "Appointments today", value: data.appointments_today_count, icon: CalendarClock, href: "/appointments",
      context: data.appointments_today?.[0] ? `Next at ${fmtTime(data.appointments_today[0].time)} · ${data.appointments_today[0].patient}` : "No more appointments today" },
    clinical && { label: "Critical results", value: data.critical_results_7d, icon: FlaskConical, href: "/labs", tone: "high" as const,
      context: `${data.abnormal_results_7d ?? 0} abnormal in the last 7 days` },
    clinical && { label: "Recently discharged", value: data.discharges_30d, icon: DoorOpen, href: "#discharged",
      context: "Last 30 days" },
    data.ai_queries_24h !== undefined && { label: "AI questions today", value: data.ai_queries_24h, icon: MessageSquareText, href: "/admin",
      context: "Every answer is traced" },
    data.denied_events_24h !== undefined && { label: "Blocked access attempts", value: data.denied_events_24h, icon: ShieldOff, href: "/admin",
      context: "Last 24 hours" },
    data.documents_indexed !== undefined && (!clinical || data.ai_queries_24h !== undefined) && { label: "Knowledge documents", value: data.documents_indexed, icon: FileText, href: "/documents",
      context: "Available to the assistant" },
  ].filter(Boolean) as { label: string; value: number | undefined; icon: React.ElementType; href?: string; context: string; tone?: "high" }[] : [];

  return (
    <>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <p className="text-sm text-muted">{today}</p>
          <h1 className="mt-1 text-[30px] font-semibold leading-tight text-ink">
            {greeting(now)}{user ? `, ${firstName(user.full_name)}` : ""}
          </h1>
          <p className="mt-1 text-[15px] text-muted">
            {clinical ? "Here is what needs your attention today." : "Here is today at the front desk."}
          </p>
        </div>
        {can(PERMS.ai) && (
          <Link href="/assistant" tabIndex={-1}>
            <Button><Bot className="h-4 w-4" /> Ask the assistant</Button>
          </Link>
        )}
      </div>

      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && !data && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-[118px] rounded-xl border border-line bg-panel p-5"><Skeleton lines={3} /></div>)}
          </div>
          <div className="h-72 rounded-xl border border-line bg-panel p-5"><Skeleton lines={7} /></div>
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <Attention data={data} now={now} />

          <div className={cn("grid grid-cols-2 gap-3 sm:gap-4", summaries.length === 3 ? "lg:grid-cols-3" : "xl:grid-cols-4")}>
            {summaries.map((s, i) => <Summary key={s.label} {...s} i={i + 1} />)}
          </div>

          {(data.census || data.recent_discharges) && (
            <div className="grid gap-6 xl:grid-cols-3">
              {data.census && (
                <Panel id="admitted" title="Admitted patients" count={data.inpatients ?? data.census.length}
                  description="Most recent admissions first" href="/patients" linkLabel="All patients"
                  className="xl:col-span-2" style={{ "--i": 5 } as React.CSSProperties}>
                  {data.census.length === 0 ? <EmptyState title="No patients are admitted right now" /> : (
                    <ul>
                      {data.census.map((c) => {
                        const alert = flagged.get(c.patient_id);
                        const day = dayOfStay(c.admitted_at, now);
                        return (
                          <Row key={c.patient_id} href={`/patients/${c.patient_id}${alert ? "?tab=labs" : ""}`}>
                            <Avatar name={c.name} tone={alert ? "alert" : "neutral"} />
                            <span className="min-w-0 flex-1">
                              <span className="flex min-w-0 items-center gap-2">
                                <span className="truncate text-sm font-medium text-ink">{c.name}</span>
                                <span className="hidden shrink-0 font-mono text-[11px] text-faint sm:inline">{c.mrn}</span>
                                {alert && (
                                  <span className="hidden shrink-0 items-center gap-1 rounded-full bg-high-tint px-2 text-[12px] font-medium leading-5 text-high ring-1 ring-inset ring-high-edge sm:flex">
                                    <AlertCircle className="h-3.5 w-3.5" aria-hidden />{alert.test} {resultValue(alert)}
                                  </span>
                                )}
                              </span>
                              <span className="block truncate text-[13px] text-muted">{c.reason}</span>
                              {alert && (
                                <span className="mt-1 flex w-fit items-center gap-1 rounded-full bg-high-tint px-2 text-[12px] font-medium leading-5 text-high ring-1 ring-inset ring-high-edge sm:hidden">
                                  <AlertCircle className="h-3.5 w-3.5" aria-hidden />{alert.test} {resultValue(alert)}
                                </span>
                              )}
                            </span>
                            <span className="hidden w-32 shrink-0 truncate text-[13px] text-muted lg:block">
                              {c.ward ? `Ward ${c.ward}` : c.department}
                            </span>
                            <span className="tabular w-14 shrink-0 text-right text-[13px] text-ink-2">Day {day}</span>
                          </Row>
                        );
                      })}
                    </ul>
                  )}
                </Panel>
              )}

              {data.recent_discharges && (
                <Panel id="discharged" title="Recently discharged" count={data.discharges_30d ?? data.recent_discharges.length}
                  description={riskTab === "predictions" ? "Review readmission risk" : "Last 30 days"}
                  className="self-start" style={{ "--i": 6 } as React.CSSProperties}>
                  {data.recent_discharges.length === 0 ? <EmptyState title="No discharges in the last 30 days" /> : (
                    <ul>
                      {data.recent_discharges.map((d) => (
                        <Row key={`${d.patient_id}-${d.discharged_at}`} href={`/patients/${d.patient_id}?tab=${riskTab}`}>
                          <Avatar name={d.name} />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-ink">{d.name}</span>
                            <span className="block truncate text-[13px] text-muted">
                              {fmtDate(d.discharged_at)} · {titleCase(d.disposition)}
                            </span>
                          </span>
                        </Row>
                      ))}
                    </ul>
                  )}
                </Panel>
              )}
            </div>
          )}

          {data.appointments_today && (
            <Panel title="Today's appointments" count={data.appointments_today_count ?? 0} href="/appointments" linkLabel="Full schedule"
              style={{ "--i": 7 } as React.CSSProperties}>
              {data.appointments_today.length === 0 ? (
                <p className="border-t border-line px-5 py-4 text-sm text-muted">No appointments are scheduled for today.</p>
              ) : (
                <ul className="grid lg:grid-cols-2">
                  {data.appointments_today.map((a) => (
                    <li key={a.id} className="border-t border-line lg:[&:nth-child(even)]:border-l">
                      <Link href={`/patients/${a.patient_id}`} className="group flex items-center gap-4 px-5 py-3 transition-colors hover:bg-sunken">
                        <span className="tabular w-14 shrink-0 rounded-lg bg-info-tint py-1.5 text-center text-[13px] font-semibold text-info">
                          {fmtTime(a.time)}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-ink">{a.patient}</span>
                          <span className="block truncate text-[13px] text-muted">{a.reason} · {a.doctor}</span>
                        </span>
                        <StatusBadge status={a.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
        </div>
      )}
    </>
  );
}
