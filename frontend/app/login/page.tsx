"use client";

import { ArrowRight, BookOpenCheck, Check, Eye, EyeOff, FlaskConical, Sparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Wordmark } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";

/* Demo accounts in the seeded hospital. */
const ACCOUNTS = [
  { email: "dr.rao@careflow.demo", name: "Dr. Rao", role: "General Medicine" },
  { email: "dr.mensah@careflow.demo", name: "Dr. Mensah", role: "Cardiology" },
  { email: "nurse.kim@careflow.demo", name: "Nurse Kim", role: "Nurse" },
  { email: "reception@careflow.demo", name: "Front desk", role: "Reception" },
  { email: "admin@careflow.demo", name: "Hospital admin", role: "Administrator" },
] as const;

function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState<string>(ACCOUNTS[0].email);
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
    <form onSubmit={submit} className="space-y-5">
      <Field label="Email">
        <Input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} className="h-11" required />
      </Field>
      <Field label="Password">
        <div className="relative">
          <Input
            type={reveal ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-11 pr-11"
            required
          />
          <button
            type="button"
            onClick={() => setReveal((v) => !v)}
            aria-label={reveal ? "Hide password" : "Show password"}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-faint transition-colors hover:bg-raised hover:text-ink"
          >
            {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </Field>
      {error ? <ErrorState error={error} compact /> : null}
      <Button type="submit" className="h-11 w-full text-[15px]" loading={busy}>
        Sign in <ArrowRight className="h-4 w-4" aria-hidden />
      </Button>

      <div className="pt-3">
        <div className="flex items-center gap-3 text-xs text-muted">
          <span className="h-px flex-1 bg-line" aria-hidden />
          Or try a demo account
          <span className="h-px flex-1 bg-line" aria-hidden />
        </div>
        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {ACCOUNTS.map((a) => {
            const selected = email === a.email;
            return (
              <button
                key={a.email}
                type="button"
                onClick={() => setEmail(a.email)}
                aria-pressed={selected}
                className={cn(
                  "flex min-w-0 items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-[border-color,background,box-shadow] duration-150",
                  selected
                    ? "border-accent bg-accent-tint shadow-[0_0_0_3px_rgba(11,125,110,0.12)]"
                    : "border-line bg-panel hover:border-line-strong hover:bg-sunken",
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                    selected ? "bg-accent text-white" : "bg-raised text-ink-2",
                  )}
                  aria-hidden
                >
                  {selected ? <Check className="h-4 w-4" /> : a.name.replace(/^(Dr\.|Nurse)\s*/, "").slice(0, 1)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-[13px] font-medium text-ink">{a.name}</span>
                  <span className="block truncate text-xs text-muted">{a.role}</span>
                </span>
              </button>
            );
          })}
        </div>
        <p className="mt-4 text-xs leading-relaxed text-muted">All demo accounts use the demo password from the project README.</p>
      </div>
    </form>
  );
}

/** A still of the product at work: the kind of cited answer the assistant gives. Synthetic content. */
function ProductStill() {
  return (
    <div className="relative mx-auto w-full max-w-[460px]" aria-hidden>
      <div className="rounded-2xl bg-white p-5 text-ink shadow-[0_30px_60px_-20px_rgba(0,0,0,0.45)]">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-tint text-[13px] font-semibold text-accent">AS</span>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold">Ananya Sharma</div>
            <div className="text-xs text-muted">Ward 3B · Type 2 diabetes, day 4</div>
          </div>
          <span className="rounded-full bg-warn-tint px-2 py-0.5 text-[11px] font-medium text-warn ring-1 ring-inset ring-warn-edge">Admitted</span>
        </div>
        <div className="mt-4 rounded-xl bg-sunken p-3.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-ai">
            <Sparkles className="h-3.5 w-3.5" /> Assistant
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">
            HbA1c was 8.9% on admission, above the 7% target in the diabetes guideline
            <span className="mx-0.5 rounded bg-ai-tint px-1 text-[11px] font-medium text-ai">S1</span>. Metformin is
            continued; no allergy conflicts are recorded
            <span className="mx-0.5 rounded bg-info-tint px-1 text-[11px] font-medium text-info">R2</span>.
          </p>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-2">
            <FlaskConical className="h-3.5 w-3.5 text-high" />
            <span className="text-muted">Glucose</span>
            <span className="ml-auto font-semibold text-high">268 mg/dL</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-2">
            <BookOpenCheck className="h-3.5 w-3.5 text-accent" />
            <span className="text-muted">Sources</span>
            <span className="ml-auto font-semibold text-ink">2 cited</span>
          </div>
        </div>
      </div>
      <div className="absolute -right-8 -top-14 hidden rounded-xl bg-white px-3.5 py-2.5 shadow-[0_18px_40px_-14px_rgba(0,0,0,0.45)] xl:block">
        <div className="text-[11px] text-muted">Readmission risk</div>
        <div className="mt-0.5 flex items-baseline gap-2">
          <span className="font-display text-[22px] font-semibold leading-none text-ink">24%</span>
          <span className="text-[11px] font-medium text-warn">Moderate</span>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen grid-cols-1 bg-panel lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden min-w-0 flex-col overflow-hidden bg-rail px-12 py-10 text-white lg:flex">
        <Wordmark tone="light" size="lg" />

        <div className="my-auto py-10">
          <h1 className="max-w-xl text-[44px] font-semibold leading-[1.08] tracking-[-0.025em] text-white">
            Everything your care team needs, in one calm workspace.
          </h1>
          <p className="mt-5 max-w-lg text-[16px] leading-relaxed text-[#b9cfcf]">
            Patients, appointments, lab results and prescriptions together, with an assistant that answers from
            the hospital&apos;s own records and shows where every answer came from.
          </p>
          <div className="mt-16">
            <ProductStill />
          </div>
        </div>

        <p className="text-[13px] text-rail-muted">Demonstration with synthetic patients. Not for clinical use.</p>
      </section>

      <section className="flex min-w-0 items-center justify-center px-6 py-10 sm:px-10">
        <div className="w-full min-w-0 max-w-[420px]">
          <div className="mb-10 lg:hidden">
            <Wordmark size="lg" />
          </div>
          <h2 className="text-[30px] font-semibold leading-tight text-ink">Welcome back</h2>
          <p className="mb-8 mt-2 text-[15px] text-muted">Sign in to continue to CareFlow.</p>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
          <p className="mt-10 text-center text-xs text-muted lg:hidden">Demonstration with synthetic patients. Not for clinical use.</p>
        </div>
      </section>
    </main>
  );
}
