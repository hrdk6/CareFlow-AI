"use client";

import { useState } from "react";

import { UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/form";
import { CreateDoctor } from "@/components/staff/create-doctor";
import { useApi, useDebounced } from "@/lib/hooks";
import { qs } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import type { Department, Doctor } from "@/lib/types";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export default function DoctorsPage() {
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [creating, setCreating] = useState(false);
  const term = useDebounced(q, 250);
  const { data, error, loading, reload } = useApi<Doctor[]>(`/doctors${qs({ q: term, department_id: dept })}`);
  const { data: departments } = useApi<Department[]>("/departments");
  return (
    <>
      <PageHeader title="Doctors" subtitle="Clinician directory and weekly clinic hours."
        actions={can(PERMS.users) ? <Button size="sm" onClick={() => setCreating(true)}><UserPlus className="h-3.5 w-3.5" /> New doctor</Button> : null} />
      {creating && <CreateDoctor departments={departments ?? []} onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload(); }} />}
      <div className="mb-4 flex flex-wrap gap-2">
        <Input placeholder="Search name or specialty" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" aria-label="Search doctors" />
        <Select value={dept} onChange={(e) => setDept(e.target.value)} placeholder="All departments" className="max-w-[220px]" aria-label="Department"
          options={(departments ?? []).map((d) => ({ value: d.id, label: d.name }))} />
      </div>
      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && !data && <Skeleton lines={6} />}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data?.map((d) => (
          <Card key={d.id}>
            <div className="flex items-start justify-between">
              <div>
                <div className="font-medium text-ink">{d.full_name}</div>
                <div className="text-xs text-muted">{d.specialty} · {d.department}</div>
              </div>
              <span className="font-mono text-xs text-faint">{d.staff_code}</span>
            </div>
            <div className="mt-3 grid grid-cols-7 gap-1 text-center text-[10px]">
              {DAYS.map((day) => {
                const slots = d.availability[day] ?? [];
                return (
                  <div key={day} className={slots.length ? "rounded bg-accent-tint p-1 text-accent" : "rounded bg-sunken p-1 text-faint"}>
                    <div className="font-semibold capitalize">{day}</div>
                    {slots.length ? slots.map(([s, e]) => <div key={s}>{s}–{e}</div>) : <div>—</div>}
                  </div>
                );
              })}
            </div>
            <div className="mt-3 text-xs text-muted">{d.email} · {d.phone}</div>
          </Card>
        ))}
      </div>
    </>
  );
}
