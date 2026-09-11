"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, KeyValue, PageHeader } from "@/components/ui/card";
import { ErrorState, Notice } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";

export default function SettingsPage() {
  const { user } = useAuth();
  const { data: status } = useApi<Record<string, unknown>>("/ai/status");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function change(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await api("/auth/change-password", { method: "POST", json: { current_password: current, new_password: next } });
      setDone(true);
      setCurrent("");
      setNext("");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (!user) return null;
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Profile">
          <KeyValue items={[["Name", user.full_name], ["Email", user.email], ["Role", user.role], ["Doctor profile", user.doctor_id ?? "—"]]} />
          <div className="mt-4">
            <div className="mb-1 text-xs text-slate-500">Permissions</div>
            <div className="flex flex-wrap gap-1">{user.permissions.map((p) => <Badge key={p}>{p}</Badge>)}</div>
          </div>
        </Card>
        <Card title="Change password">
          <form onSubmit={change} className="space-y-3">
            <Field label="Current password"><Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required /></Field>
            <Field label="New password" hint="At least 12 characters"><Input type="password" autoComplete="new-password" value={next} minLength={12} onChange={(e) => setNext(e.target.value)} required /></Field>
            {error ? <ErrorState error={error} compact /> : null}
            {done && <Notice tone="success">Password updated.</Notice>}
            <Button type="submit" loading={busy}>Update password</Button>
          </form>
        </Card>
        {status && (
          <Card title="AI configuration" className="lg:col-span-2">
            <KeyValue columns={3} items={Object.entries(status).map(([k, v]) => [k.replace(/_/g, " "), String(v ?? "—")])} />
            <p className="mt-3 text-xs text-slate-500">Providers are configured server-side via environment variables (CAREFLOW_LLM_PROVIDER, CAREFLOW_LLM_MODEL, …). See the README.</p>
          </Card>
        )}
      </div>
    </>
  );
}
