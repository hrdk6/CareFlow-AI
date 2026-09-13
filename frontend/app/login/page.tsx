"use client";

import { Activity, Eye, EyeOff, Lock } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";

/* The seeded demo hospital. Counts are what each account's access policy returns on the demo data. */
const ROLES = [
  { email: "dr.rao@careflow.demo", role: "Doctor", scope: "General Medicine", patients: 119, clinical: true },
  { email: "dr.mensah@careflow.demo", role: "Doctor", scope: "Cardiology", patients: 59, clinical: true },
  { email: "nurse.kim@careflow.demo", role: "Nurse", scope: "Assigned patients", patients: 18, clinical: true },
  { email: "reception@careflow.demo", role: "Reception", scope: "Registration only", patients: 241, clinical: false },
  { email: "admin@careflow.demo", role: "Administrator", scope: "Oversight, read-only", patients: 241, clinical: true },
] as const;

function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState<string>(ROLES[0].email);
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/login", { method: "POST", json: { email, password } });
      const next = params.get("next");
      window.location.href = next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Email">
        <Input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </Field>
      <Field label="Password">
        <div className="relative">
          <Input
            type={reveal ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="pr-10"
            required
          />
          <button
            type="button"
            onClick={() => setReveal((v) => !v)}
            aria-label={reveal ? "Hide password" : "Show password"}
            className="absolute right-1 top-1/2 -translate-y-1/2 rounded-sm p-1.5 text-muted transition-colors hover:bg-raised hover:text-ink"
          >
            {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </Field>
      {error ? <ErrorState error={error} compact /> : null}
      <Button type="submit" className="w-full" loading={busy}>
        <Lock className="h-4 w-4" /> Sign in
      </Button>

      <fieldset className="rounded-lg border border-line">
        <legend className="ml-3 px-1.5 font-display text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
          Demo accounts
        </legend>
        <div className="pb-1">
          {ROLES.map((r) => {
            const selected = email === r.email;
            return (
              <button
                key={r.email}
                type="button"
                onClick={() => setEmail(r.email)}
                aria-pressed={selected}
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-2 text-left transition-colors",
                  selected ? "bg-raised" : "hover:bg-panel",
                )}
              >
                <span className={cn("h-1.5 w-1.5 shrink-0", selected ? "bg-accent" : "bg-line-strong")} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-ink">{r.role}</span>
                  <span className="block truncate text-[11px] text-muted">{r.scope}</span>
                </span>
                <span className="font-mono text-[11px] text-faint">{r.email.split("@")[0]}</span>
              </button>
            );
          })}
        </div>
      </fieldset>
      <p className="text-[11px] leading-relaxed text-muted">
        Password: the <span className="font-mono text-ink-2">CAREFLOW_DEMO_PASSWORD</span> used when seeding (see README).
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen grid-cols-1 bg-field lg:grid-cols-[1.25fr_1fr]">
      <section className="hidden min-w-0 flex-col border-r border-line px-12 py-10 lg:flex">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-ok" strokeWidth={2.25} aria-hidden />
          <span className="font-display text-[20px] font-bold uppercase tracking-[0.12em] text-ink">CareFlow</span>
          <span className="font-display text-[20px] font-semibold uppercase tracking-[0.12em] text-accent">AI</span>
        </div>

        <div className="my-auto max-w-2xl py-12">
          <h1 className="font-display text-[48px] font-semibold leading-[1.02] tracking-[-0.01em] text-ink">
            One hospital record. Five different views of it, each limited to what that person may see.
          </h1>
          <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-muted">
            Access is decided inside the database, before any search, model or AI answer sees the data. The same
            question returns a different answer for every role below.
          </p>

          <div className="mt-10 grid grid-cols-5 overflow-hidden rounded-lg border border-line">
            {ROLES.map((r) => (
              <div key={r.email} className="relative border-r border-line bg-panel px-3.5 pb-3 pt-3 last:border-r-0">
                <span className={cn("absolute inset-x-0 top-0 h-px", r.clinical ? "bg-ok" : "bg-line-strong")} aria-hidden />
                <div className={cn("font-display text-[12px] font-semibold uppercase tracking-[0.1em]", r.clinical ? "text-ok" : "text-muted")}>
                  {r.role}
                </div>
                <div className="tabular mt-2 font-display text-[40px] font-semibold leading-none text-ink">{r.patients}</div>
                <div className="mt-2 text-[11px] leading-snug text-muted">
                  patients · {r.clinical ? "clinical" : "no clinical data"}
                </div>
                <div className="mt-0.5 truncate text-[11px] text-faint">{r.scope}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2.5 border-t border-line pt-5">
          <span className="h-2 w-2 bg-warn" aria-hidden />
          <p className="font-display text-[12px] font-semibold uppercase tracking-[0.08em] text-warn">
            Synthetic patients · decision support only, not for clinical use
          </p>
        </div>
      </section>

      <section className="flex min-w-0 items-center justify-center p-6">
        <div className="w-full min-w-0 max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <Activity className="h-5 w-5 text-ok" strokeWidth={2.25} aria-hidden />
            <span className="font-display text-[18px] font-bold uppercase tracking-[0.12em] text-ink">CareFlow</span>
            <span className="font-display text-[18px] font-semibold uppercase tracking-[0.12em] text-accent">AI</span>
          </div>
          <h2 className="font-display text-[30px] font-semibold leading-none text-ink">Sign in</h2>
          <p className="mb-6 mt-2 text-sm text-muted">Pick a role to see the hospital through that person&apos;s access.</p>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
