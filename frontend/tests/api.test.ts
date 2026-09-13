import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, errorMessage, qs } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

function mockFetch(status: number, body: unknown) {
  // A Response body can only be read once, so build a fresh one per call.
  const fn = vi.fn().mockImplementation(async () => new Response(body === null ? null : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("api client", () => {
  it("sends the CSRF header on writes but not on reads", async () => {
    const fetchMock = mockFetch(200, { ok: true });
    await api("/patients");
    await api("/patients", { method: "POST", json: { a: 1 } });
    const [, getInit] = fetchMock.mock.calls[0];
    const [, postInit] = fetchMock.mock.calls[1];
    expect((getInit.headers as Headers).get("X-CareFlow-CSRF")).toBeNull();
    expect((postInit.headers as Headers).get("X-CareFlow-CSRF")).toBe("1");
    expect(postInit.body).toBe('{"a":1}');
  });

  it("converts backend error envelopes into ApiError", async () => {
    mockFetch(404, { error: { code: "not_found", message: "Patient not found or not accessible", request_id: "abc123" } });
    await expect(api("/patients/7")).rejects.toMatchObject({ status: 404, code: "not_found", requestId: "abc123" });
  });

  it("formats validation issues", () => {
    const err = new ApiError(422, "validation_failed", "The request is invalid", undefined,
      { issues: [{ field: "date_of_birth", message: "must be in the past" }] });
    expect(errorMessage(err)).toBe("date_of_birth: must be in the past");
  });

  it("reports network failures clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(api("/health")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("treats the proxy's bare 500 as an unreachable backend", async () => {
    // What the Next.js rewrite returns when nothing listens on the API port.
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response("Internal Server Error", { status: 500 })));
    const err = await api("/auth/me").catch((e) => e);
    expect(err).toMatchObject({ status: 500, code: "network_error" });
    expect(errorMessage(err)).toMatch(/Cannot reach the CareFlow API/);
  });

  it("keeps the backend's own 5xx message when it sends one", async () => {
    mockFetch(500, { error: { code: "internal_error", message: "Unexpected error", request_id: "r1" } });
    await expect(api("/dashboard")).rejects.toMatchObject({ status: 500, code: "internal_error", requestId: "r1" });
  });

  it("builds query strings without empty values", () => {
    expect(qs({ q: "rao", status: "", limit: 5, x: undefined })).toBe("?q=rao&limit=5");
  });
});
