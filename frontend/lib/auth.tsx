"use client";

import { createContext, useCallback, useContext, useMemo } from "react";

import { api } from "./api";
import { useApi } from "./hooks";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  can: (...permissions: string[]) => boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { data, loading } = useApi<User>("/auth/me");
  const user = data ?? null;
  const can = useCallback((...perms: string[]) => !!user && perms.every((p) => user.permissions.includes(p)), [user]);
  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      // Full reload on purpose: signing out must discard every cached query result in memory.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
  }, []);
  const value = useMemo(() => ({ user, loading, can, logout }), [user, loading, can, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export const PERMS = {
  clinical: "patients:read_clinical",
  patientsWrite: "patients:write",
  appointmentsWrite: "appointments:write",
  clinicalWrite: "clinical:write",
  prescribe: "prescriptions:write",
  admit: "admissions:write",
  ml: "ml:read",
  ai: "ai:query",
  docsManage: "documents:manage",
  docsRead: "documents:read",
  users: "users:manage",
  audit: "audit:read",
  observe: "system:observe",
} as const;
