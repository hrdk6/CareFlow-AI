"use client";

import { AlertTriangle, ArrowLeft, Bot, CalendarPlus, Droplet } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";

import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { AppointmentsTab, LabsTab, PrescriptionsTab, RecordsTab } from "@/components/patient/clinical-tabs";
import { OverviewTab } from "@/components/patient/overview";
import { PredictionsTab } from "@/components/patient/predictions";
import { SimilarTab } from "@/components/patient/similar";
import { TimelineTab } from "@/components/patient/timeline";
import { Avatar } from "@/components/ui/avatar";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Tabs } from "@/components/ui/tabs";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { PatientClinical, PatientDemographics } from "@/lib/types";

const TAB_IDS = ["overview", "timeline", "records", "prescriptions", "labs", "appointments", "predictions", "similar", "assistant"] as const;
type TabId = (typeof TAB_IDS)[number];

const SEX: Record<string, string> = { F: "Female", M: "Male" };

function Detail({ label, children, title }: { label: string; children: React.ReactNode; title?: string }) {
  return (
    <div className="min-w-0 bg-panel px-5 py-3">
      <dt className="text-[12px] font-medium text-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-sm text-ink" title={title}>{children}</dd>
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading patient">
      <div className="h-4 w-20 rounded-full shimmer" />
      <div className="rounded-xl border border-line bg-panel p-6 shadow-e1">
        <div className="flex items-center gap-5">
          <div className="shimmer h-14 w-14 rounded-full" />
          <div className="flex-1 space-y-2.5">
            <div className="shimmer h-5 w-64 max-w-full rounded-full" />
            <div className="shimmer h-3 w-80 max-w-full rounded-full" />
          </div>
        </div>
      </div>
      <div className="rounded-xl border border-line bg-panel p-5 shadow-e1"><Skeleton lines={6} /></div>
    </div>
  );
}

export default function PatientProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  // The open tab lives in the URL: links can land on it, and Back retraces the path through a record.
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const requested = params.get("tab");
  const tab: TabId = (TAB_IDS as readonly string[]).includes(requested ?? "") ? (requested as TabId) : "overview";
  const setTab = (next: TabId) => router.push(`${pathname}?tab=${next}`, { scroll: false });
  const { data, error, loading, reload } = useApi<PatientClinical | PatientDemographics>(`/patients/${id}`);
  const clinical = can(PERMS.clinical);
  const patient = data as PatientClinical | undefined;

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <ProfileSkeleton />;
  if (!patient) return null;
  const label = `${patient.full_name} (${patient.mrn})`;
  const emergency = patient.emergency_contact_name
    ? `${patient.emergency_contact_name}${patient.emergency_contact_relation ? ` (${patient.emergency_contact_relation})` : ""}`
    : null;

  return (
    <div className="space-y-4">
      <Link href="/patients" className="group inline-flex items-center gap-1 rounded-md text-[13px] text-muted hover:text-accent">
        <ArrowLeft className="h-3.5 w-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" aria-hidden /> Patients
      </Link>

      <header className="rise overflow-hidden rounded-xl border border-line bg-panel shadow-e1">
        <div className="flex flex-wrap items-start gap-x-5 gap-y-4 p-5 sm:p-6">
          <Avatar name={patient.full_name} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
              <h1 className="text-[26px] font-semibold leading-tight text-ink">{patient.full_name}</h1>
              <span className="rounded-md bg-raised px-1.5 font-mono text-[12px] leading-6 text-ink-2">{patient.mrn}</span>
              <StatusBadge status={patient.status} />
              {patient.is_synthetic && <Badge tone="warning">Synthetic</Badge>}
            </div>
            <p className="mt-1 text-sm text-muted">
              {patient.age} years · {SEX[patient.sex] ?? "Other"} · Born {fmtDate(patient.date_of_birth)} · {patient.primary_department ?? "No department"}
            </p>
            {clinical && patient.allergies && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <span className="mr-1 text-[12px] font-medium text-muted">Allergies</span>
                {patient.allergies.length === 0 ? <Badge tone="success" dot>None known</Badge> :
                  patient.allergies.map((a) => (
                    <Badge key={a.substance} tone="danger" title={`${a.reaction} (${a.severity})`}>
                      <AlertTriangle className="h-3 w-3" aria-hidden /> {a.substance} · {a.reaction}
                    </Badge>
                  ))}
                {patient.blood_type && <Badge className="ml-1"><Droplet className="h-3 w-3" aria-hidden /> Blood group {patient.blood_type}</Badge>}
              </div>
            )}
          </div>
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            {can(PERMS.appointmentsWrite) && (
              <Link href={`/appointments?patient=${patient.id}`} tabIndex={-1}>
                <Button variant="secondary"><CalendarPlus className="h-4 w-4" /> Book appointment</Button>
              </Link>
            )}
            {can(PERMS.ai) && <Button onClick={() => setTab("assistant")}><Bot className="h-4 w-4" /> Ask the assistant</Button>}
          </div>
        </div>
        {/* Hairline cells: the gap shows the line colour behind white cells. */}
        <dl className="grid grid-cols-1 gap-px border-t border-line bg-line sm:grid-cols-2 xl:grid-cols-4">
          <Detail label="Phone">{patient.phone ?? "—"}</Detail>
          <Detail label="Email" title={patient.email ?? undefined}>{patient.email ?? "—"}</Detail>
          <Detail label="Preferred language">{patient.preferred_language}</Detail>
          <Detail label="Emergency contact" title={emergency ?? undefined}>
            <span className="block truncate">{emergency ?? "—"}</span>
            {/* A phone number is never truncated: it gets its own line. */}
            {patient.emergency_contact_phone && <span className="block text-[13px] text-muted">{patient.emergency_contact_phone}</span>}
          </Detail>
        </dl>
      </header>

      {/* The tab bar stays under the app header while a long record scrolls. */}
      <div className="sticky top-16 z-20 -mx-4 bg-field/85 px-4 backdrop-blur-md md:-mx-8 md:px-8">
        <Tabs<TabId> active={tab} onChange={setTab} tabs={[
          { id: "overview", label: "Overview" },
          { id: "timeline", label: "Timeline", hidden: !clinical },
          { id: "records", label: "Records", hidden: !clinical },
          { id: "prescriptions", label: "Prescriptions", hidden: !clinical },
          { id: "labs", label: "Labs", hidden: !clinical },
          { id: "appointments", label: "Appointments" },
          { id: "predictions", label: "Predictions", hidden: !can(PERMS.ml, PERMS.clinical) },
          { id: "similar", label: "Similar patients", hidden: !can(PERMS.ml, PERMS.clinical) },
          { id: "assistant", label: "AI assistant", hidden: !can(PERMS.ai) },
        ]} />
      </div>

      <div key={tab} className="animate-panel-in" role="tabpanel">
        {tab === "overview" && <OverviewTab patient={patient} clinical={clinical} onOpen={(t) => setTab(t as TabId)} onChanged={reload} />}
        {tab === "timeline" && <TimelineTab patientId={patient.id} />}
        {tab === "records" && <RecordsTab patientId={patient.id} />}
        {tab === "prescriptions" && <PrescriptionsTab patientId={patient.id} />}
        {tab === "labs" && <LabsTab patientId={patient.id} />}
        {tab === "appointments" && <AppointmentsTab patientId={patient.id} />}
        {tab === "predictions" && <PredictionsTab patientId={patient.id} />}
        {tab === "similar" && <SimilarTab patientId={patient.id} />}
        {tab === "assistant" && (
          <section className="rounded-xl border border-line bg-panel shadow-e1">
            <AssistantPanel patientId={patient.id} patientLabel={label} patientName={patient.first_name} />
          </section>
        )}
      </div>
    </div>
  );
}
