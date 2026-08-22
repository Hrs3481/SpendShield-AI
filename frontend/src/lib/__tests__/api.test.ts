/**
 * The fetch client is the only place the frontend touches the network, so its
 * error handling is what decides whether a failure shows a useful message or a
 * blank screen.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, clearToken, formatINR, getToken, onUnauthorized, setToken } from "../api";

function mockFetch(response: Partial<Response> & { jsonBody?: unknown }) {
  const impl = vi.fn(async () => ({
    ok: response.ok ?? true,
    status: response.status ?? 200,
    statusText: response.statusText ?? "OK",
    json: async () => {
      if (response.jsonBody === undefined) throw new Error("no body");
      return response.jsonBody;
    },
  })) as unknown as typeof fetch;
  vi.stubGlobal("fetch", impl);
  return impl as unknown as ReturnType<typeof vi.fn>;
}

describe("formatINR", () => {
  it("uses Indian digit grouping, not thousands grouping", () => {
    // ₹1,20,000 — the lakh grouping. Intl 'en-US' would give ₹120,000.
    expect(formatINR(120000)).toBe("₹1,20,000");
  });

  it("rounds to whole rupees by default", () => {
    expect(formatINR(280.22)).toBe("₹280");
  });

  it("can show paise when asked", () => {
    expect(formatINR(280.22, true)).toBe("₹280.22");
  });

  it("handles zero and negatives", () => {
    expect(formatINR(0)).toBe("₹0");
    expect(formatINR(-500)).toContain("500");
  });
});

describe("token storage", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips and clears", () => {
    expect(getToken()).toBeNull();
    setToken("abc");
    expect(getToken()).toBe("abc");
    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe("request error handling", () => {
  beforeEach(() => localStorage.clear());

  it("surfaces the API's detail string", async () => {
    mockFetch({ ok: false, status: 422, jsonBody: { detail: "price: must be greater than 0" } });
    await expect(api.getSafeToSpend()).rejects.toMatchObject({
      status: 422,
      message: "price: must be greater than 0",
    });
  });

  it("falls back to status text when the body has no JSON", async () => {
    mockFetch({ ok: false, status: 500, statusText: "Internal Server Error" });
    await expect(api.getSafeToSpend()).rejects.toMatchObject({ status: 500 });
  });

  it("reports an unreachable backend rather than throwing a raw TypeError", async () => {
    // fetch rejects only on network failure, never on a 4xx/5xx.
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const err = await api.getSafeToSpend().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.message).toMatch(/backend running/i);
  });

  it("clears the token and broadcasts on a 401, so the app can drop to login", async () => {
    setToken("expired-token");
    const handler = vi.fn();
    const off = onUnauthorized(handler);

    mockFetch({ ok: false, status: 401, jsonBody: { detail: "Could not validate credentials" } });
    await api.getSafeToSpend().catch(() => undefined);

    expect(getToken()).toBeNull();
    expect(handler).toHaveBeenCalledOnce();
    off();
  });

  it("does not broadcast a 401 when there was no token to begin with", async () => {
    const handler = vi.fn();
    const off = onUnauthorized(handler);
    mockFetch({ ok: false, status: 401, jsonBody: { detail: "nope" } });
    await api.getSafeToSpend().catch(() => undefined);
    expect(handler).not.toHaveBeenCalled();
    off();
  });

  it("attaches the bearer token when one is stored", async () => {
    setToken("my-token");
    const f = mockFetch({ ok: true, jsonBody: { safe_to_spend_today: 100 } });
    await api.getSafeToSpend();
    const headers = (f.mock.calls[0][1] as RequestInit).headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("sends registration credentials in the body, never the query string", async () => {
    const f = mockFetch({ ok: true, jsonBody: { access_token: "t", token_type: "bearer" } });
    await api.register("a@b.com", "a-good-password", "A B");

    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).not.toContain("password");
    expect(url).not.toContain("a@b.com");
    expect(JSON.parse(init.body as string)).toMatchObject({
      email: "a@b.com",
      password: "a-good-password",
    });
  });

  it("logs in with form encoding, as the OAuth2 password flow requires", async () => {
    const f = mockFetch({ ok: true, jsonBody: { access_token: "t", token_type: "bearer" } });
    await api.login("a@b.com", "pw");
    const init = f.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"])
      .toBe("application/x-www-form-urlencoded");
    expect(init.body).toContain("username=a%40b.com");
  });

  it("returns undefined for a 204 instead of trying to parse a body", async () => {
    setToken("t");
    mockFetch({ ok: true, status: 204 });
    await expect(api.deleteTransaction("some-id")).resolves.toBeUndefined();
  });
});
