"use client";

import { ArrowUpRight, Bot } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtDate, fmtTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";

interface CriticalResult {
  id: number; patient_id: number; mrn: string; name: string; test: string; code: string; value: number | null;
  value_text: string | null; unit: string | null; reference_low: number | null; reference_high: number | null; collected_at: string;
}

interface Station {
  role: string; role_label: string; patients_visible: number; generated_at?: string;
  appointments_today?: { id: number; time: string; patient: string; patient_id: number; mrn: string; doctor: string; reason: string; status: string }[];
  appointments_today_count?: number; inpatients?: number; discharges_7d?: number; discharges_30d?: number;
  documents_indexed?: number; ai_queries_24h?: number; denied_events_24h?: number;
  critical_results?: CriticalResult[]; critical_results_7d?: number; abnormal_results_7d?: number;
  census?: { patient_id: number; mrn: string; name: string; reason: string; admitted_at: string; department: string; ward: string | null }[];
  recent_discharges?: { patient_id: number; mrn: string; name: string; reason: string; discharged_at: string; disposition: string }[];
}

type Channel = "ok" | "info" | "warn" | "high" | "ai" | "accent";
type ReadingState = "live" | "stale" | "untimed" | "restricted";

/* The channel table, read once: label colour, the top rule and the sweep all come from here. */
const CHANNEL: Record<Channel, { text: string; rule: string; varName: string }> = {
  ok: { text: "text-ok", rule: "bg-ok", varName: "var(--color-ok)" },
  info: { text: "text-info", rule: "bg-info", varName: "var(--color-info)" },
  warn: { text: "text-warn", rule: "bg-warn", varName: "var(--color-warn)" },
  high: { text: "text-high", rule: "bg-high", varName: "var(--color-high)" },
  ai: { text: "text-ai", rule: "bg-ai", varName: "var(--color-ai)" },
  accent: { text: "text-accent", rule: "bg-accent", varName: "var(--color-accent)" },
};

const STATE_LABEL: Record<ReadingState, { label: string; tone: string; lamp: string }> = {
  live: { label: "Live", tone: "text-muted", lamp: "bg-ok" },
  stale: { label: "Stale", tone: "text-warn", lamp: "bg-warn" },
  untimed: { label: "No timestamp", tone: "text-muted", lamp: "bg-faint" },
  restricted: { label: "Not permitted", tone: "text-faint", lamp: "bg-line-strong" },
};

const REFRESH_MS = 60_000;
const STALE_MS = 3 * 60_000;
const ALARMS_ON_MOBILE = 3;

function ago(iso: string, now: number): string {
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

function dayOfStay(admittedAt: string, now: number): number {
  return Math.max(1, Math.floor((now - new Date(admittedAt).getTime()) / 86_400_000) + 1);
}

function resultValue(r: CriticalResult): string {
  return r.value !== null ? `${r.value}${r.unit ? ` ${r.unit}` : ""}` : r.value_text ?? "—";
}

/** How far a result sits outside its reference range, in range-widths. Drives alarm ordering. */
function severity(r: CriticalResult): number {
  if (r.value === null || r.reference_low === null || r.reference_high === null) return 0;
  const width = r.reference_high - r.reference_low || 1;
  return Math.max((r.reference_low - r.value) / width, (r.value - r.reference_high) / width, 0);
}

function readingState(generatedAt: string | undefined, now: number): ReadingState {
  if (!generatedAt) return "untimed";
  return now - new Date(generatedAt).getTime() > STALE_MS ? "stale" : "live";
}

function StateTag({ state, compact }: { state: ReadingState; compact?: boolean }) {
  const s = STATE_LABEL[state];
  return (
    <span className={cn("flex shrink-0 items-center gap-1.5 font-display text-[11px] font-semibold uppercase tracking-[0.12em]", s.tone)}
      title={s.label}>
      <span className={cn("h-1.5 w-1.5", s.lamp)} aria-hidden />
      <span className={compact ? "sr-only sm:not-sr-only" : undefined}>{s.label}</span>
    </span>
  );
}

/** A channel cell inside the strip. Its position never changes; a refresh sweeps across it and a
 *  changed value settles in place from the channel colour. */
function ChannelCell({ label, value, unit, context, contextShort, channel, sweepKey, href, state }: {
  label: string; value: number | undefined; unit: string; context?: React.ReactNode; contextShort?: React.ReactNode;
  channel: Channel; sweepKey: string; href?: string; state: ReadingState;
}) {
  const ch = CHANNEL[channel];
  const restricted = state === "restricted";
  const body = (
    <>
      <span className={cn("absolute inset-x-0 top-0 h-px", restricted ? "bg-line-strong" : ch.rule)} aria-hidden />
      {!restricted && <span key={sweepKey} className="sweep-line" style={{ "--sweep-color": ch.varName } as React.CSSProperties} aria-hidden />}
      {/* One fixed-height label row, so every numeric in the strip shares a baseline. */}
      <div className="flex h-5 items-center justify-between gap-2">
        <span className={cn("min-w-0 truncate font-display text-[12px] font-semibold uppercase tracking-[0.1em] sm:text-[13px]", restricted ? "text-faint" : ch.text)}>
          {label}
        </span>
        <StateTag state={state} compact />
      </div>
      <div className="mt-2 flex items-end gap-2">
        {restricted || value === undefined ? (
          <span className="font-display text-[44px] font-semibold leading-[0.85] text-faint sm:text-[60px]" aria-label="No data for your role">—</span>
        ) : (
          <span
            key={`${label}-${value}`}
            className="value-settle tabular font-display text-[44px] font-semibold leading-[0.85] text-ink sm:text-[60px]"
            style={{ "--settle-color": ch.varName } as React.CSSProperties}
          >
            {value}
          </span>
        )}
        <span className="mb-0.5 font-display text-[12px] font-semibold uppercase tracking-[0.08em] text-muted sm:text-[13px]">{unit}</span>
        {href && !restricted && <ArrowUpRight className="mb-1 ml-auto h-4 w-4 text-faint transition-colors group-hover:text-ink" aria-hidden />}
      </div>
      <div className="mt-2.5 min-h-[18px] text-xs text-muted">
        {restricted ? (
          <><span className="sm:hidden">Clinical only</span><span className="hidden sm:inline">Requires clinical access</span></>
        ) : (
          <>
            <span className="block truncate sm:hidden">{contextShort ?? context}</span>
            <span className="hidden truncate sm:block">{context}</span>
          </>
        )}
      </div>
    </>
  );
  const cell = "group relative block min-w-0 overflow-hidden bg-panel px-3.5 pb-3 pt-3.5 sm:px-4";
  return href && !restricted
    ? <Link href={href} className={cn(cell, "transition-colors duration-150 hover:bg-raised")}>{body}</Link>
    : <div className={cell}>{body}</div>;
}

/** A panel section of the instrument: a channel-labelled header over flush content. */
function Section({ title, meta, action, className, children, id }: {
  title: React.ReactNode; meta?: React.ReactNode; action?: React.ReactNode; className?: string; children: React.ReactNode; id?: string;
}) {
  return (
    <section id={id} className={cn("min-w-0 bg-panel", className)}>
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <div className="min-w-0">
          <h2 className="truncate font-display text-[13px] font-semibold uppercase tracking-[0.1em] text-ink-2">{title}</h2>
          {meta && <p className="truncate text-xs text-muted">{meta}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

/** The priority alarm bar: every critical result, ordered by how far it sits outside its reference
 *  range. The lamp flashes at the high-priority rate; entries never clip. */
function AlarmBar({ data, now, clinical }: { data: Station; now: number; clinical: boolean }) {
  if (!clinical) {
    return (
      <div className="flex items-center gap-3 rounded-sm border border-line bg-panel px-4 py-2.5">
        <span className="h-2.5 w-2.5 shrink-0 bg-faint" aria-hidden />
        <span className="font-display text-[13px] font-semibold uppercase tracking-[0.1em] text-muted">Alarm feed</span>
        <span className="text-xs text-muted">Critical results are shown to clinical roles only.</span>
      </div>
    );
  }
  const results = [...(data.critical_results ?? [])].sort(
    (a, b) => severity(b) - severity(a) || new Date(b.collected_at).getTime() - new Date(a.collected_at).getTime(),
  );
  const abnormal = (
    <span className="tabular font-display text-[12px] font-semibold uppercase tracking-[0.08em] text-warn">
      {data.abnormal_results_7d ?? 0} abnormal · 7 d
    </span>
  );
  if (results.length === 0) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-sm border border-ok-edge bg-ok-tint px-4 py-2.5">
        <span className="h-2.5 w-2.5 shrink-0 bg-ok" aria-hidden />
        <span className="font-display text-[13px] font-semibold uppercase tracking-[0.1em] text-ok">No critical results</span>
        <span className="text-xs text-ink-2">Last 7 days, patients within your access.</span>
        <span className="ml-auto">{abnormal}</span>
      </div>
    );
  }
  const hiddenOnMobile = Math.max(0, results.length - ALARMS_ON_MOBILE);
  return (
    <section aria-label="Critical results" className="overflow-hidden rounded-sm border border-high-edge bg-high-tint">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-high-edge px-4 py-2">
        <span className="alarm-lamp h-2.5 w-2.5 shrink-0 bg-high" aria-hidden />
        <span className="font-display text-[14px] font-bold uppercase tracking-[0.12em] text-high">Critical</span>
        <span className="tabular font-display text-[14px] font-bold text-ink">{data.critical_results_7d}</span>
        <span className="hidden text-xs text-ink-2 md:inline">Last 7 days · ordered by distance outside the reference range</span>
        <span className="ml-auto flex items-center gap-4">
          {abnormal}
          <Link href="/labs" className="font-display text-[12px] font-semibold uppercase tracking-[0.1em] text-ink hover:underline">All results</Link>
        </span>
      </header>
      <ul className="grid gap-px bg-high-edge/70 sm:grid-cols-2 xl:grid-cols-4">
        {results.map((r, i) => (
          <li key={r.id} className={cn("bg-high-tint", i >= ALARMS_ON_MOBILE && "hidden sm:block")}>
            <Link href={`/patients/${r.patient_id}?tab=labs`} className="flex h-full items-start gap-3 px-4 py-2.5 transition-colors hover:bg-[#3b2224]">
              <span className="tabular shrink-0 font-display text-[18px] font-bold uppercase leading-tight text-high">
                {r.code} {resultValue(r)}
              </span>
              <span className="min-w-0 leading-tight">
                <span className="block truncate text-[13px] font-medium text-ink">
                  {r.name} <span className="font-mono text-[11px] text-muted">{r.mrn}</span>
                </span>
                <span className="block truncate text-[11px] text-ink-2">
                  {r.reference_low !== null && r.reference_high !== null ? `ref ${r.reference_low}–${r.reference_high} · ` : ""}{ago(r.collected_at, now)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {hiddenOnMobile > 0 && (
        <Link href="/labs" className="block border-t border-high-edge px-4 py-2 font-display text-[12px] font-semibold uppercase tracking-[0.1em] text-high sm:hidden">
          + {hiddenOnMobile} more critical
        </Link>
      )}
    </section>
  );
}

function LiveStamp({ generatedAt, now }: { generatedAt?: string; now: number }) {
  const state = readingState(generatedAt, now);
  return (
    <span className="flex items-center gap-2" role="status">
      <StateTag state={state} />
      {generatedAt && <span className="tabular text-xs text-muted">updated {fmtTime(generatedAt)} UTC</span>}
    </span>
  );
}

export default function CentralStationPage() {
  const { user, can } = useAuth();
  const { data, error, loading, reload } = useApi<Station>("/dashboard");
  const [now, setNow] = useState(() => Date.now());

  // A monitor never goes quiet: refetch on a fixed cadence and keep the clock that ages each value.
  useEffect(() => {
    const refresh = setInterval(reload, REFRESH_MS);
    const clock = setInterval(() => setNow(Date.now()), 20_000);
    return () => { clearInterval(refresh); clearInterval(clock); };
  }, [reload]);

  const clinical = can(PERMS.clinical);
  const riskTab = can(PERMS.ml) ? "predictions" : "overview";
  const sweepKey = data?.generated_at ?? "initial";
  const reading = readingState(data?.generated_at, now);
  const stateFor = (value: number | undefined): ReadingState => (value === undefined ? "restricted" : reading);
  const alarmByPatient = new Map<number, CriticalResult>();
  for (const r of data?.critical_results ?? []) {
    const known = alarmByPatient.get(r.patient_id);
    if (!known || severity(r) > severity(known)) alarmByPatient.set(r.patient_id, r);
  }

  return (
    <>
      <PageHeader
        title="Central station"
        subtitle={`${user?.full_name ?? ""}${data ? ` · ${data.role_label}` : ""} · every channel is limited to the ${data?.patients_visible ?? "…"} patients you are authorised to see.`}
        actions={
          <>
            {data && <LiveStamp generatedAt={data.generated_at} now={now} />}
            {can(PERMS.ai) && (
              <Link href="/assistant"><Button variant="secondary"><Bot className="h-4 w-4" /> Ask the assistant</Button></Link>
            )}
          </>
        }
      />
      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && !data && <Skeleton lines={6} />}

      {data && (
        <div className="space-y-4">
          <AlarmBar data={data} now={now} clinical={clinical} />

          {/* One instrument: channel cells share their rules instead of floating as separate cards. */}
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-line bg-line xl:grid-cols-4">
            <ChannelCell label="Inpatients" unit="patients" channel="ok" sweepKey={sweepKey} value={data.inpatients}
              state={stateFor(data.inpatients)} href="#census"
              context={`${data.discharges_7d ?? 0} discharged in the last 7 days`}
              contextShort={`${data.discharges_7d ?? 0} out · 7 d`} />
            <ChannelCell label="Outpatients today" unit="appts" channel="info" sweepKey={sweepKey} value={data.appointments_today_count}
              state={stateFor(data.appointments_today_count)} href="/appointments"
              context={data.appointments_today?.[0] ? `Next at ${fmtTime(data.appointments_today[0].time)} UTC · ${data.appointments_today[0].patient}` : "None remaining today"}
              contextShort={data.appointments_today?.[0] ? `Next ${fmtTime(data.appointments_today[0].time)} UTC` : "None today"} />
            <ChannelCell label="Critical results" unit="results" channel="high" sweepKey={sweepKey} value={data.critical_results_7d}
              state={stateFor(data.critical_results_7d)} href="/labs"
              context={`Last 7 days · ${data.abnormal_results_7d ?? 0} abnormal`}
              contextShort={`7 d · ${data.abnormal_results_7d ?? 0} abnormal`} />
            <ChannelCell label="Recent discharges" unit="patients" channel="warn" sweepKey={sweepKey} value={data.discharges_30d}
              state={stateFor(data.discharges_30d)} href="#discharges"
              context="Last 30 days · readmission-risk review"
              contextShort="30 d · risk review" />
          </div>

          {data.ai_queries_24h !== undefined && (
            <div className="grid gap-px overflow-hidden rounded-sm border border-line bg-line sm:grid-cols-3">
              <ChannelCell label="AI queries · 24 h" unit="queries" channel="ai" sweepKey={sweepKey} value={data.ai_queries_24h}
                state={reading} href="/admin" context="Traced with route, sources and latency" />
              <ChannelCell label="Denied access · 24 h" unit="events" channel="high" sweepKey={sweepKey} value={data.denied_events_24h}
                state={reading} href="/admin" context="Blocked attempts recorded in the audit log" />
              <ChannelCell label="Indexed documents" unit="docs" channel="accent" sweepKey={sweepKey} value={data.documents_indexed}
                state={reading} href="/documents" context="Searchable by the assistant" />
            </div>
          )}

          {(data.census || data.recent_discharges) && (
            <div className="grid gap-px overflow-hidden rounded-sm border border-line bg-line xl:grid-cols-3">
              {data.census && (
                <Section id="census" title={`Census · ${data.inpatients ?? data.census.length} admitted`} className="xl:col-span-2"
                  action={<span className="font-display text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">Day of stay</span>}>
                  {data.census.length === 0 ? <EmptyState title="No current inpatients" /> : (
                    <ul>
                      {data.census.map((c) => {
                        const alarm = alarmByPatient.get(c.patient_id);
                        return (
                          <li key={c.patient_id} className="border-b border-line last:border-b-0">
                            <Link href={`/patients/${c.patient_id}${alarm ? "?tab=labs" : ""}`}
                              className={cn("grid grid-cols-[64px_1fr_auto] items-center gap-3 px-4 py-2.5 transition-colors hover:bg-raised sm:grid-cols-[76px_1fr_170px_56px] sm:gap-4",
                                alarm && "bg-high-tint/40")}>
                              <span className={cn("rounded-sm border px-1.5 py-1 text-center font-mono text-[11px] font-medium",
                                alarm ? "border-high-edge bg-high-tint text-high" : "border-ok-edge bg-ok-tint text-ok")}>
                                {c.ward ?? "—"}
                              </span>
                              <span className="min-w-0">
                                <span className="block truncate text-sm font-medium text-ink">
                                  {c.name} <span className="font-mono text-[11px] font-normal text-muted">{c.mrn}</span>
                                </span>
                                <span className="block truncate text-xs text-muted">{c.reason}</span>
                                {alarm && (
                                  <span className="mt-0.5 flex items-center gap-1.5 font-display text-[12px] font-bold uppercase text-high sm:hidden">
                                    <span className="alarm-lamp h-1.5 w-1.5 bg-high" aria-hidden />{alarm.code} {resultValue(alarm)}
                                  </span>
                                )}
                              </span>
                              {/* The bed row carries its own alarm, as a central station would. */}
                              <span className="hidden min-w-0 sm:block">
                                {alarm ? (
                                  <span className="flex items-center gap-2">
                                    <span className="alarm-lamp h-2 w-2 shrink-0 bg-high" aria-hidden />
                                    <span className="tabular truncate font-display text-[15px] font-bold uppercase text-high">{alarm.code} {resultValue(alarm)}</span>
                                  </span>
                                ) : (
                                  <span className="block truncate text-xs text-muted">{c.department}</span>
                                )}
                              </span>
                              <span className="tabular text-right font-display text-[26px] font-semibold leading-none text-ink">
                                {dayOfStay(c.admitted_at, now)}
                              </span>
                            </Link>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Section>
              )}

              {data.recent_discharges && (
                <Section id="discharges" title={`Recent discharges · ${data.discharges_30d ?? data.recent_discharges.length}`}
                  meta="Last 30 days · check readmission risk">
                  {data.recent_discharges.length === 0 ? <EmptyState title="No recent discharges" /> : (
                    <ul>
                      {data.recent_discharges.map((d) => (
                        <li key={`${d.patient_id}-${d.discharged_at}`} className="border-b border-line last:border-b-0">
                          <Link href={`/patients/${d.patient_id}?tab=${riskTab}`}
                            className="group flex items-start gap-3 px-4 py-2.5 transition-colors hover:bg-raised">
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 bg-warn" aria-hidden />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium text-ink">
                                {d.name} <span className="font-mono text-[11px] font-normal text-muted">{d.mrn}</span>
                              </span>
                              <span className="block truncate text-xs text-muted">{d.reason}</span>
                              <span className="tabular block text-[11px] text-ink-2">{fmtDate(d.discharged_at)} · to {titleCase(d.disposition)}</span>
                            </span>
                            <span className="mt-0.5 flex shrink-0 items-center gap-1 font-display text-[11px] font-semibold uppercase tracking-[0.1em] text-faint transition-colors group-hover:text-accent">
                              {riskTab === "predictions" ? "Risk" : "Open"} <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
              )}
            </div>
          )}

          {data.appointments_today && (
            <div className="overflow-hidden rounded-sm border border-line">
              <Section title={`Outpatients today · ${data.appointments_today_count ?? 0}`}
                action={<Link href="/appointments" className="font-display text-[12px] font-semibold uppercase tracking-[0.1em] text-accent hover:underline">Full schedule</Link>}>
                {data.appointments_today.length === 0 ? (
                  <p className="px-4 py-3 text-sm text-muted">No outpatient appointments are scheduled for today.</p>
                ) : (
                  <ul className="grid lg:grid-cols-2">
                    {data.appointments_today.map((a) => (
                      <li key={a.id} className="border-b border-line lg:odd:border-r">
                        <Link href={`/patients/${a.patient_id}`} className="flex items-center gap-4 px-4 py-2.5 transition-colors hover:bg-raised">
                          <span className="tabular w-12 font-display text-[18px] font-semibold text-info">{fmtTime(a.time)}</span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-ink">
                              {a.patient} <span className="font-mono text-[11px] font-normal text-muted">{a.mrn}</span>
                            </span>
                            <span className="block truncate text-xs text-muted">{a.reason} · {a.doctor}</span>
                          </span>
                          <StatusBadge status={a.status} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </div>
          )}
        </div>
      )}
    </>
  );
}
