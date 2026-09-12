"use client";

import { Activity, ArrowRight, BrainCircuit, Eye, EyeOff, FileSearch, Lock, ShieldCheck, Stethoscope } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";

const DEMO_ACCOUNTS = [
  ["dr.rao@careflow.demo", "Doctor", "General Medicine · 119 patients"],
  ["dr.mensah@careflow.demo", "Doctor", "Cardiology · 59 patients"],
  ["nurse.kim@careflow.demo", "Nurse", "Assigned patients only"],
  ["reception@careflow.demo", "Reception", "Everyone, no clinical data"],
  ["admin@careflow.demo", "Administrator", "Accounts, audit, oversight"],
] as const;

const HIGHLIGHTS = [
  { icon: Stethoscope, title: "One authorized workspace", text: "Records, timelines, appointments, prescriptions and labs." },
  { icon: BrainCircuit, title: "Predictions you can question", text: "Readmission risk and length of stay with the factors behind them." },
  { icon: FileSearch, title: "Answers with citations", text: "Hybrid search over hospital documents, every claim traceable." },
] as const;

function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState("dr.rao@careflow.demo");
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
            className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          >
            {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </Field>
      {error ? <ErrorState error={error} compact /> : null}
      <Button type="submit" className="w-full" loading={busy}>
        <Lock className="h-4 w-4" /> Sign in
      </Button>

      <div className="rounded-xl border border-line bg-slate-50/70 p-3">
        <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
          Demo accounts · pick a role
        </p>
        <div className="grid gap-0.5">
          {DEMO_ACCOUNTS.map(([addr, role, detail]) => (
            <button
              key={addr}
              type="button"
              onClick={() => setEmail(addr)}
              className={cn(
                "group flex min-w-0 items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors",
                email === addr ? "bg-white shadow-e1 ring-1 ring-inset ring-brand-200" : "hover:bg-white/80",
              )}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium text-slate-800">{role}</span>
                <span className="block truncate text-[11px] text-muted">{detail}</span>
              </span>
              <ArrowRight
                className={cn(
                  "h-3.5 w-3.5 shrink-0 transition-all",
                  email === addr ? "text-brand-600" : "-translate-x-1 text-slate-300 opacity-0 group-hover:translate-x-0 group-hover:opacity-100",
                )}
              />
            </button>
          ))}
        </div>
        <p className="mt-2 px-1 text-[11px] leading-relaxed text-muted">
          Password: the <span className="font-mono">CAREFLOW_DEMO_PASSWORD</span> used when seeding (see README).
        </p>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel: layered gradients over a faint grid, so the dark side has depth rather than flat ink. */}
      <section className="relative hidden min-w-0 flex-col justify-between overflow-hidden bg-brand-950 p-10 text-brand-50 lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.16]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
            backgroundSize: "44px 44px",
            maskImage: "radial-gradient(ellipse 80% 60% at 30% 20%, black, transparent 75%)",
          }}
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -left-24 top-1/3 h-[28rem] w-[28rem] rounded-full bg-brand-500/25 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-32 right-0 h-96 w-96 rounded-full bg-brand-400/15 blur-3xl"
          aria-hidden
        />

        <div className="relative flex items-center gap-2.5 text-lg font-semibold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 shadow-e2">
            <Activity className="h-4.5 w-4.5 text-white" />
          </span>
          CareFlow<span className="-ml-1.5 font-normal text-brand-300">AI</span>
        </div>

        <div className="relative max-w-lg">
          <h1 className="text-[2.6rem] font-semibold leading-[1.1] tracking-tight text-white">
            Clinical information, retrieval and prediction — in one authorized workspace.
          </h1>
          <ul className="mt-9 space-y-5">
            {HIGHLIGHTS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3.5">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-inset ring-white/15">
                  <Icon className="h-4.5 w-4.5 text-brand-200" />
                </span>
                <span>
                  <span className="block text-sm font-medium text-white">{title}</span>
                  <span className="mt-0.5 block text-sm leading-relaxed text-brand-100/80">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative flex items-center gap-2 text-xs text-brand-200/80">
          <ShieldCheck className="h-4 w-4 shrink-0" />
          Portfolio demonstration with fully synthetic patients. Not for clinical use.
        </p>
      </section>

      <section className="flex min-w-0 items-center justify-center bg-canvas p-6">
        <div className="w-full min-w-0 max-w-sm">
          <div className="mb-7 flex items-center gap-2.5 text-lg font-semibold text-slate-900 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700">
              <Activity className="h-4 w-4 text-white" />
            </span>
            CareFlow<span className="-ml-1.5 font-normal text-brand-600">AI</span>
          </div>
          <h2 className="text-[22px] font-semibold tracking-tight text-slate-900">Sign in</h2>
          <p className="mb-6 mt-1.5 text-sm text-muted">Each demo account shows the product through a different role.</p>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
