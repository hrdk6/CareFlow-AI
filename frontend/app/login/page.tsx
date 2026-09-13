"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ErrorState } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";

/* Demo accounts in the seeded hospital. */
const ACCOUNTS = [
  { email: "dr.rao@careflow.demo", name: "Dr. Rao", role: "Doctor · General Medicine" },
  { email: "dr.mensah@careflow.demo", name: "Dr. Mensah", role: "Doctor · Cardiology" },
  { email: "nurse.kim@careflow.demo", name: "Nurse Kim", role: "Nurse" },
  { email: "reception@careflow.demo", name: "Front desk", role: "Reception" },
  { email: "admin@careflow.demo", name: "Hospital admin", role: "Administrator" },
] as const;

const INPUT =
  "w-full rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-800 shadow-sm transition-all " +
  "placeholder:text-neutral-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-emerald-700";

function DemoAccount({ account, selected, onSelect, className }: {
  account: (typeof ACCOUNTS)[number]; selected: boolean; onSelect: () => void; className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "group relative flex items-center gap-3 rounded-xl bg-white p-3 text-left transition-all",
        selected
          ? "border-2 border-emerald-600 shadow-sm ring-1 ring-emerald-600 hover:bg-emerald-50/40"
          : "border border-neutral-200 hover:border-neutral-300 hover:bg-neutral-50",
        className,
      )}
    >
      {selected ? (
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0a5c48] text-white">
          <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden>
            <path d="M4.5 12.75l6 6 9-13.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      ) : (
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-neutral-100 text-sm font-semibold text-neutral-700 group-hover:bg-neutral-200" aria-hidden>
          {account.name.replace(/^(Dr\.|Nurse)\s*/, "").charAt(0)}
        </span>
      )}
      <span className="min-w-0 pr-1">
        <span className="block truncate text-sm font-semibold leading-snug text-neutral-900">{account.name}</span>
        <span className="block truncate text-xs text-neutral-500">{account.role}</span>
      </span>
    </button>
  );
}

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

  // Four accounts in a two-column grid; the administrator spans the full width beneath.
  const grid = ACCOUNTS.slice(0, 4);
  const admin = ACCOUNTS[4];

  return (
    <>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700" htmlFor="email">Email</label>
          <input
            id="email" name="email" type="email" autoComplete="username" placeholder="name@careflow.demo" required
            value={email} onChange={(e) => setEmail(e.target.value)} className={INPUT}
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700" htmlFor="password">Password</label>
          <div className="relative">
            <input
              id="password" name="password" type={reveal ? "text" : "password"} autoComplete="current-password"
              placeholder="••••••••" required value={password} onChange={(e) => setPassword(e.target.value)}
              className={cn(INPUT, "pr-11")}
            />
            <button
              type="button"
              onClick={() => setReveal((v) => !v)}
              aria-label={reveal ? "Hide password" : "Show password"}
              aria-pressed={reveal}
              className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-neutral-400 transition-colors hover:text-neutral-600"
            >
              {reveal ? (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden>
                  <path d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden>
                  <path d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          </div>
        </div>
        {error ? <ErrorState error={error} compact /> : null}
        <div className="pt-2">
          <button
            type="submit"
            disabled={busy}
            aria-busy={busy || undefined}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#0a5c48] px-4 py-3.5 text-base font-medium text-white shadow-sm transition-all hover:bg-[#074b3a] focus:outline-none focus:ring-2 focus:ring-emerald-800 focus:ring-offset-2 active:bg-[#053d2f] disabled:opacity-70"
          >
            {busy ? (
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden>
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="3" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
            ) : null}
            <span>Sign in</span>
            <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24" aria-hidden>
              <path d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </form>

      <div className="relative my-7">
        <div className="absolute inset-0 flex items-center" aria-hidden>
          <div className="w-full border-t border-neutral-200" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-white px-3 font-medium text-neutral-500">Or try a demo account</span>
        </div>
      </div>

      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {grid.map((a) => (
            <DemoAccount key={a.email} account={a} selected={email === a.email} onSelect={() => setEmail(a.email)} />
          ))}
        </div>
        <DemoAccount account={admin} selected={email === admin.email} onSelect={() => setEmail(admin.email)} className="w-full" />
      </div>

      <p className="mt-6 text-center text-xs text-neutral-500">All demo accounts use the demo password from the project README.</p>
    </>
  );
}

/** The glowing care core: orbiting rings, a medical cross and a live ECG trace. Decorative. */
function CareCore() {
  return (
    <div className="flex w-full items-center justify-center py-6 sm:py-8" aria-hidden>
      <div className="animate-floating relative flex h-64 w-64 items-center justify-center sm:h-72 sm:w-72">
        <div className="animate-core-pulse pointer-events-none absolute inset-0 rounded-full bg-gradient-to-tr from-emerald-500/20 via-teal-400/20 to-transparent blur-2xl" />

        <svg className="animate-spin-slow absolute inset-0 h-full w-full opacity-70" viewBox="0 0 260 260">
          <defs>
            <linearGradient id="ringGradientOuter" x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#059669" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#34d399" stopOpacity="0.9" />
            </linearGradient>
          </defs>
          <circle cx="130" cy="130" r="120" fill="none" stroke="url(#ringGradientOuter)" strokeDasharray="14 10 30 8 4 12" strokeWidth="1.5" />
          <circle cx="250" cy="130" r="4.5" fill="#34d399" style={{ filter: "drop-shadow(0 0 6px #34d399)" }} />
          <circle cx="40" cy="70" r="3" fill="#10b981" />
          <circle cx="70" cy="210" r="3.5" fill="#059669" />
        </svg>

        <svg className="animate-spin-reverse-slow absolute inset-4 h-[calc(100%-32px)] w-[calc(100%-32px)] opacity-60" viewBox="0 0 220 220">
          <circle cx="110" cy="110" r="98" fill="none" stroke="#10b981" strokeDasharray="4 6" strokeOpacity="0.3" strokeWidth="1.2" />
          <circle cx="110" cy="12" r="3.5" fill="#6ee7b7" style={{ filter: "drop-shadow(0 0 5px #6ee7b7)" }} />
          <circle cx="190" cy="160" r="2.5" fill="#10b981" />
        </svg>

        <div className="relative flex h-36 w-36 items-center justify-center rounded-full border border-emerald-500/40 bg-gradient-to-b from-neutral-900/90 to-black shadow-[0_0_40px_rgba(16,185,129,0.35)] backdrop-blur-md">
          <div className="absolute h-24 w-24 rounded-full bg-emerald-500/25 blur-lg" />
          <div className="relative z-10 flex items-center justify-center">
            <svg className="h-16 w-16 text-emerald-400 drop-shadow-[0_0_15px_rgba(52,211,153,0.9)]" fill="currentColor" viewBox="0 0 64 64">
              <path d="M26 10a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v13h13a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H38v13a3 3 0 0 1-3 3h-6a3 3 0 0 1-3-3V38H13a3 3 0 0 1-3-3v-6a3 3 0 0 1 3-3h13V10z" fillOpacity="0.95" />
              <circle cx="32" cy="32" r="4.5" fill="#ffffff" style={{ filter: "drop-shadow(0 0 6px #ffffff)" }} />
            </svg>
          </div>
          <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 144 144">
            <path className="ecg-path" d="M12 72h42l6 -16l8 32l8 -22l6 10h50" fill="none" stroke="#6ee7b7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />
          </svg>
        </div>

        {/* The Stitch comp read "99.8% Synthetic Accuracy"; the product has no such figure, so the pill states a true property. */}
        <div className="absolute -top-1 right-3 flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-neutral-900/90 px-3 py-1 font-mono text-[11px] text-emerald-300 shadow-md backdrop-blur-sm">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 motion-reduce:hidden" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          Every answer cited
        </div>
        <div className="absolute -bottom-2 left-2 flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-neutral-900/90 px-3 py-1 font-mono text-[11px] text-emerald-300 shadow-md backdrop-blur-sm">
          <svg className="h-3 w-3 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
            <path clipRule="evenodd" fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" />
          </svg>
          EHR Grounded Model
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen w-full grid-cols-1 overflow-x-hidden bg-black font-sans text-slate-100 antialiased selection:bg-emerald-500 selection:text-white lg:grid-cols-2">
      <section className="relative flex flex-col justify-between overflow-hidden border-b border-neutral-900 bg-black p-8 sm:p-12 lg:border-b-0 lg:border-r lg:p-16 xl:p-20">
        <div aria-hidden className="pointer-events-none absolute left-1/2 top-1/3 h-[480px] w-[480px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-500/10 blur-[110px]" />
        <div aria-hidden className="pointer-events-none absolute bottom-10 left-10 h-[300px] w-[300px] rounded-full bg-teal-600/10 blur-[90px]" />

        <header className="relative z-10">
          <div className="inline-flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] shadow-lg shadow-teal-900/30">
              <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.3} viewBox="0 0 24 24" aria-hidden>
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <span className="flex items-center gap-1.5 text-2xl font-bold tracking-tight text-white">
              CareFlow
              <span className="rounded-md border border-emerald-800/50 bg-emerald-950 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-emerald-400">AI</span>
            </span>
          </div>
        </header>

        <div className="relative z-10 my-auto flex max-w-xl flex-col items-start py-10">
          <CareCore />
          <h1 className="mt-4 font-sans text-3xl font-bold leading-[1.18] tracking-tight text-white [text-wrap:wrap] sm:text-4xl lg:text-[44px]">
            Everything your care team needs, in one calm workspace.
          </h1>
          <p className="mt-5 max-w-lg text-base font-normal leading-relaxed text-neutral-400 sm:text-lg">
            Patients, appointments, lab results and prescriptions together, with an assistant that answers from the
            hospital&apos;s own records and shows where every answer came from.
          </p>
        </div>

        <footer className="relative z-10 pt-4 text-xs text-neutral-500 sm:text-sm">
          Demonstration with synthetic patients. Not for clinical use.
        </footer>
      </section>

      <section className="flex flex-col items-center justify-center bg-white p-8 text-slate-900 sm:p-12 lg:p-16 xl:p-24">
        <div className="w-full max-w-md">
          <div className="mb-8">
            <h2 className="font-sans text-3xl font-bold tracking-tight text-neutral-900 [text-wrap:wrap] sm:text-[32px]">Welcome back</h2>
            <p className="mt-2 text-sm text-neutral-500 sm:text-base">Sign in to continue to CareFlow.</p>
          </div>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
