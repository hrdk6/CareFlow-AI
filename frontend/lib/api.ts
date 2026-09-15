/** Typed client for the CareFlow API (proxied at /api by next.config.ts). */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
    public details?: { issues?: { field: string; message: string }[] } & Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

const BASE = "/api";
const UNREACHABLE = "Cannot reach the CareFlow API. Check that the backend is running.";

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  // Custom header required by the backend for cookie-authenticated writes (CSRF defence).
  if (method !== "GET") headers.set("X-CareFlow-CSRF", "1");
  let body = options.body;
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }
  let response: Response;
  try {
    response = await fetch(BASE + path, { ...options, method, headers, body, credentials: "same-origin", cache: "no-store" });
  } catch {
    throw new ApiError(0, "network_error", UNREACHABLE);
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!response.ok) {
    const err = (data as { error?: { code?: string; message?: string; request_id?: string; details?: ApiError["details"] } })?.error;
    if (response.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") {
      // Full reload on purpose: an expired session must drop all client-side state, not just change route.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    // The backend always answers errors with a JSON envelope. A 5xx without one came from the Next.js proxy,
    // which returns a bare 500 when nothing is listening on the API port.
    if (!err && response.status >= 500) throw new ApiError(response.status, "network_error", UNREACHABLE);
    // A 429 without the envelope came from the hosting platform in front of the API, not from CareFlow's own
    // limits (those explain themselves), so say what happened instead of a bare status code.
    if (!err && response.status === 429) {
      const wait = Number(response.headers.get("retry-after"));
      throw new ApiError(429, "upstream_rate_limited", "The server is receiving too many requests right now. " +
        (wait > 0 ? `Try again in ${Math.ceil(wait)} seconds.` : "Wait a minute, then try again."));
    }
    throw new ApiError(response.status, err?.code ?? "http_error", err?.message ?? `Request failed (${response.status})`,
      err?.request_id, err?.details);
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const issues = error.details?.issues;
    if (issues?.length) return issues.map((i) => `${i.field || "request"}: ${i.message}`).join("; ");
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong";
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}
