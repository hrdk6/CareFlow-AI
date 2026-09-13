"use client";

import { AlertTriangle, ArrowLeft, Bot, CalendarPlus, Droplet, Users } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";

import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { AppointmentsTab, LabsTab, PrescriptionsTab, RecordsTab } from "@/components/patient/clinical-tabs";
import { OverviewTab } from "@/components/patient/overview";
import { PredictionsTab } from "@/components/patient/predictions";
import { SimilarTab } from "@/components/patient/similar";
import { TimelineTab } from "@/components/patient/timeline";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, KeyValue } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Tabs } from "@/components/ui/tabs";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { PatientClinical, PatientDemographics } from "@/lib/types";

const TAB_IDS = ["overview", "timeline", "records", "prescriptions", "labs", "appointments", "predictions", "similar", "assistant"] as const;
type TabId = (typeof TAB_IDS)[number];

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
  if (loading && !data) return <Skeleton lines={8} />;
  if (!patient) return null;
  const label = `${patient.full_name} (${patient.mrn})`;

  return (
    <div className="space-y-4">
      <Link href="/patients" className="inline-flex items-center gap-1 text-xs text-muted hover:text-accent"><ArrowLeft className="h-3.5 w-3.5" /> Patients</Link>
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-tint text-lg font-semibold text-accent">
              {patient.first_name[0]}{patient.last_name[0]}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold text-ink">{patient.full_name}</h1>
                <span className="font-mono text-sm text-muted">{patient.mrn}</span>
                <StatusBadge status={patient.status} />
                {patient.is_synthetic && <Badge tone="warning">Synthetic</Badge>}
              </div>
              <div className="mt-1 text-sm text-muted">
                {patient.age} years · {patient.sex === "F" ? "Female" : patient.sex === "M" ? "Male" : "Other"} · born {fmtDate(patient.date_of_birth)} · {patient.primary_department ?? "No department"}
              </div>
              {clinical && patient.allergies && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {patient.allergies.length === 0 ? <Badge tone="success">No known allergies</Badge> :
                    patient.allergies.map((a) => (
                      <Badge key={a.substance} tone="danger" title={`${a.reaction} (${a.severity})`}><AlertTriangle className="h-3 w-3" /> {a.substance}: {a.reaction}</Badge>
                    ))}
                  {patient.blood_type && <Badge><Droplet className="h-3 w-3" /> {patient.blood_type}</Badge>}
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {can(PERMS.appointmentsWrite) && (
              <Link href={`/appointments?patient=${patient.id}`}><Button variant="secondary"><CalendarPlus className="h-4 w-4" /> Book</Button></Link>
            )}
            {can(PERMS.ai) && <Button onClick={() => setTab("assistant")}><Bot className="h-4 w-4" /> Ask AI</Button>}
          </div>
        </div>
        <div className="mt-4 border-t border-line pt-4">
          <KeyValue columns={3} items={[
            ["Phone", patient.phone], ["Email", patient.email], ["Language", patient.preferred_language],
            ["Emergency contact", patient.emergency_contact_name ? `${patient.emergency_contact_name} (${patient.emergency_contact_relation ?? "—"})` : null],
            ["Emergency phone", patient.emergency_contact_phone],
            ["Care team", clinical && patient.care_team?.length ? (
              <span title={patient.care_team.map((c) => `${c.name} (${titleCase(c.care_role)})`).join(", ")}><Users className="mr-1 inline h-3.5 w-3.5 align-[-2px] text-faint" />{patient.care_team.map((c) => `${c.name} (${titleCase(c.care_role)})`).join(", ")}</span>
            ) : "—"],
          ]} />
        </div>
      </Card>

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

      <div>
        {tab === "overview" && <OverviewTab patient={patient} clinical={clinical} onOpen={(t) => setTab(t as TabId)} onChanged={reload} />}
        {tab === "timeline" && <TimelineTab patientId={patient.id} />}
        {tab === "records" && <RecordsTab patientId={patient.id} />}
        {tab === "prescriptions" && <PrescriptionsTab patientId={patient.id} />}
        {tab === "labs" && <LabsTab patientId={patient.id} />}
        {tab === "appointments" && <AppointmentsTab patientId={patient.id} />}
        {tab === "predictions" && <PredictionsTab patientId={patient.id} />}
        {tab === "similar" && <SimilarTab patientId={patient.id} />}
        {tab === "assistant" && <Card><AssistantPanel patientId={patient.id} patientLabel={label} /></Card>}
      </div>
    </div>
  );
}
