"use client";

import { Activity, Lock, ShieldCheck } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";

const DEMO_ACCOUNTS = [
  ["admin@careflow.demo", "Administrator"],
  ["dr.rao@careflow.demo", "Doctor · General Medicine"],
  ["dr.mensah@careflow.demo", "Doctor · Cardiology"],
  ["nurse.kim@careflow.demo", "Nurse · assigned patients"],
  ["reception@careflow.demo", "Reception"],
] as const;

function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState("dr.rao@careflow.demo");
  const [password, setPassword] = useState("");
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
        <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </Field>
      {error ? <ErrorState error={error} compact /> : null}
      <Button type="submit" className="w-full" loading={busy}>
        <Lock className="h-4 w-4" /> Sign in
      </Button>
      <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-3">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Demo accounts (synthetic)</p>
        <div className="grid gap-1">
          {DEMO_ACCOUNTS.map(([addr, label]) => (
            <button key={addr} type="button" onClick={() => setEmail(addr)}
              className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 rounded px-2 py-1 text-left text-xs hover:bg-white">
              <span className="min-w-0 truncate font-mono text-slate-700">{addr}</span>
              <span className="text-slate-500">{label}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-slate-500">Password: the value of CAREFLOW_DEMO_PASSWORD used when seeding (see README).</p>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.1fr_1fr]">
      <section className="hidden min-w-0 flex-col justify-between bg-brand-900 p-10 text-brand-50 lg:flex">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <Activity className="h-6 w-6 text-brand-200" /> CareFlow AI
        </div>
        <div className="max-w-md">
          <h1 className="text-3xl font-semibold leading-tight text-white">Clinical information, retrieval and prediction — in one authorized workspace.</h1>
          <ul className="mt-6 space-y-2 text-sm text-brand-100">
            <li>• Patient records, timelines, appointments and prescriptions</li>
            <li>• Readmission and length-of-stay models with explanations</li>
            <li>• Hybrid-search knowledge base with verifiable citations</li>
            <li>• Every AI answer grounded in data you are permitted to see</li>
          </ul>
        </div>
        <p className="flex items-center gap-2 text-xs text-brand-200">
          <ShieldCheck className="h-4 w-4" /> Portfolio demonstration with fully synthetic patients. Not for clinical use.
        </p>
      </section>
      <section className="flex min-w-0 items-center justify-center p-6">
        <div className="w-full min-w-0 max-w-sm">
          <div className="mb-6 lg:hidden flex items-center gap-2 text-lg font-semibold text-brand-800">
            <Activity className="h-5 w-5" /> CareFlow AI
          </div>
          <h2 className="text-xl font-semibold text-slate-900">Sign in</h2>
          <p className="mb-6 mt-1 text-sm text-slate-500">Use a demo account to explore each role.</p>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
